// Intermediario para actualizar el Arcón de Pancheim (Cloudflare Worker).
//
// Corre la acción "Actualizar inventario" del repo de la página:
//  - sola, cada 30 minutos (Cron Trigger del Worker), porque el programador de GitHub se atrasa horas;
//  - cuando alguien toca "Actualizar" en la página, si la última corrida fue hace más de MIN_MINUTOS.
//
// La clave de GitHub (GH_TOKEN) vive solo en los secretos del Worker: un token fine-grained con permiso
// "Actions: Read and write" sobre este repo y nada más. La página nunca la ve.
const REPO = "pancheim/pancheim.github.io";
const WORKFLOW = "actualizar.yml";
const ORIGIN = "https://pancheim.github.io";
const MIN_MINUTOS = 15;   // el botón no dispara si la última corrida empezó hace menos que esto

async function gh(env, path, init = {}) {
  return fetch(`https://api.github.com/repos/${REPO}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${env.GH_TOKEN}`, Accept: "application/vnd.github+json",
      "User-Agent": "arcon-pancheim-worker", "X-GitHub-Api-Version": "2022-11-28", ...(init.headers || {}) },
  });
}

async function lastRun(env) {
  const r = await gh(env, `/actions/workflows/${WORKFLOW}/runs?per_page=1`);
  if (!r.ok) throw new Error(`GitHub ${r.status}`);
  const run = (await r.json()).workflow_runs[0];
  return run ? { created: run.created_at, status: run.status, conclusion: run.conclusion } : null;
}

async function dispatch(env) {
  const r = await gh(env, `/actions/workflows/${WORKFLOW}/dispatches`, { method: "POST", body: JSON.stringify({ ref: "main" }) });
  if (r.status !== 204) throw new Error(`GitHub ${r.status}`);
}

const minutesSince = iso => (Date.now() - Date.parse(iso)) / 60000;
const cors = { "Access-Control-Allow-Origin": ORIGIN, "Access-Control-Allow-Methods": "GET, POST", "Content-Type": "application/json" };
const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: cors });

export default {
  // Cada 30 minutos: corre la acción salvo que ya esté corriendo.
  async scheduled(event, env, ctx) {
    const run = await lastRun(env);
    if (run && run.status !== "completed") return;
    await dispatch(env);
  },

  // GET  /estado     -> última corrida (para habilitar el botón)
  // POST /actualizar -> corre la acción si la última empezó hace más de MIN_MINUTOS y no está corriendo
  async fetch(request, env) {
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });
    const path = new URL(request.url).pathname;
    try {
      const run = await lastRun(env);
      const ago = run ? minutesSince(run.created) : Infinity;
      const busy = run && run.status !== "completed";
      if (path === "/estado" && request.method === "GET")
        return json({ ultima: run, minutos: Math.round(ago), corriendo: !!busy, puede: !busy && ago >= MIN_MINUTOS, espera: MIN_MINUTOS });
      if (path === "/actualizar" && request.method === "POST") {
        if (busy) return json({ ok: false, motivo: "Ya se está actualizando." }, 409);
        if (ago < MIN_MINUTOS) return json({ ok: false, motivo: `Se actualizó hace ${Math.round(ago)} min. Probá en ${Math.ceil(MIN_MINUTOS - ago)} min.` }, 429);
        await dispatch(env);
        return json({ ok: true }, 202);
      }
      return json({ ok: false, motivo: "No existe." }, 404);
    } catch (e) {
      // El detalle es el codigo de GitHub (401 clave mala o vencida, 403/404 sin permiso o sin aprobar), nunca la clave.
      return json({ ok: false, motivo: "No pude hablar con GitHub.", detalle: env.GH_TOKEN ? e.message : "Falta el secreto GH_TOKEN." }, 502);
    }
  },
};
