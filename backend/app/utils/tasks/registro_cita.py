from __future__ import annotations

import json
import logging
import os
import random
import time
from pathlib import Path
from typing import Any, Optional

from flask_mailman import EmailMessage

from app.infrastructure.celery_app import BaseTask, celery_app

logger = logging.getLogger(__name__)

# Importar playwright-stealth si está disponible
try:
    from playwright_stealth import Stealth
    STEALTH_AVAILABLE = True
    logger.info("✅ playwright-stealth disponible y cargado")
except ImportError:
    STEALTH_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.error("❌ playwright-stealth NO disponible. Instala con: pip install playwright-stealth")
    logger.error("💣 Sin stealth → estás vendido a la detección")

# FrameLocator (iframe) o Frame (documento / iframe resuelto)
RootLike = Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
STATE_FILE = PROJECT_ROOT / "instance" / "registro_cita_state.json"


def _human_delay(min_seconds: float = 2.0, max_seconds: float = 5.0) -> None:
    """Añade un delay aleatorio para simular comportamiento humano."""
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


def _simulate_mouse_movement(page) -> None:
    """Simula movimientos aleatorios del mouse para parecer más humano."""
    try:
        # Movimientos aleatorios del mouse
        for _ in range(random.randint(2, 5)):
            x = random.randint(100, 1200)
            y = random.randint(100, 800)
            page.mouse.move(x, x, y)
            time.sleep(random.uniform(0.1, 0.3))
    except Exception:
        pass


def _apply_stealth(page) -> None:
    """
    Aplica técnicas avanzadas de stealth para evadir detección.
    """
    if STEALTH_AVAILABLE:
        logger.info("🛡️ Aplicando playwright-stealth...")
        try:
            stealth_obj = Stealth()
            stealth_obj.apply(page)
            logger.info("✅ playwright-stealth aplicado correctamente")
        except Exception as e:
            logger.warning(f"⚠️ Error aplicando stealth: {e}")
    else:
        logger.warning("⚠️ playwright-stealth no disponible - usando técnicas manuales")
    
    # Técnicas manuales adicionales
    try:
        # Ocultar propiedades de automatización
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: () => ['es-ES', 'es', 'en'],
            });
            
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32',
            });
            
            window.chrome = {
                runtime: {},
            };
            
            Object.defineProperty(navigator, 'permissions', {
                get: () => ({
                    query: () => Promise.resolve({ state: 'granted' }),
                }),
            });
        """)
        
        # Simular fingerprint más realista
        page.evaluate("""
            // Evitar detección de headless
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 4,
            });
            
            // Simular device memory
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8,
            });
            
            // Ocultar atributos de automatización
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        """)
        
        logger.info("✅ Técnicas stealth manuales aplicadas")
        
    except Exception as e:
        logger.error(f"❌ Error aplicando stealth: {e}")
        logger.error("💣 Esto puede causar detección inmediata")


def _get_realistic_user_agent() -> str:
    """Devuelve un User Agent realista y actualizado."""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
    ]
    return random.choice(user_agents)


def _load_state() -> dict:
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception:
        logger.exception("No se pudo leer %s", STATE_FILE)
    return {"already_notified": False}


def _save_state(state: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception:
        logger.exception("No se pudo guardar %s", STATE_FILE)


def _iter_frames(page):
    main = page.main_frame
    yield main
    for fr in page.frames:
        if fr != main:
            yield fr


def _detect_result_in_frame(frame) -> tuple[bool, bool]:
    sin_citas = frame.locator("p.mf-msg__info").filter(
        has_text="no hay citas disponibles"
    )
    if sin_citas.count() > 0:
        return False, True

    try:
        body = frame.locator("body").inner_text().lower()
        if "no hay citas disponibles" in body:
            return False, True
    except Exception:
        pass

    sede_opts = frame.locator("select#idSede option[value]:not([value=''])")
    try:
        n = sede_opts.count()
    except Exception:
        n = 0
    if n > 0:
        return True, False
    return False, False


def _detect_result(page) -> tuple[bool, bool]:
    """Devuelve (hay_citas_disponibles, mensaje_sin_citas). Busca en todos los frames."""
    wait_ms = int(os.getenv("REGISTRO_CITA_WAIT_MS", "120000"))
    deadline = time.monotonic() + wait_ms / 1000.0
    while time.monotonic() < deadline:
        for frame in _iter_frames(page):
            try:
                hay, sin_c = _detect_result_in_frame(frame)
                if hay or sin_c:
                    return hay, sin_c
            except Exception:
                continue
        page.wait_for_timeout(500)

    logger.warning("Timeout esperando contenido tras solicitar cita.")
    for frame in _iter_frames(page):
        try:
            hay, sin_c = _detect_result_in_frame(frame)
            if hay or sin_c:
                return hay, sin_c
        except Exception:
            continue
    return False, False


def _fill_force() -> bool:
    return os.getenv("REGISTRO_CITA_FILL_FORCE", "true").lower() in ("1", "true", "yes")


def _prepare_locator_attached(locator, timeout_ms: int) -> None:
    """Espera al nodo en el DOM y desplaza a vista (no exige visible)."""
    locator.wait_for(state="attached", timeout=timeout_ms)
    try:
        locator.scroll_into_view_if_needed(timeout=min(15000, timeout_ms))
    except Exception:
        pass


def _goto_wait_until() -> str:
    v = (os.getenv("REGISTRO_CITA_GOTO_WAIT_UNTIL") or "domcontentloaded").strip().lower()
    if v in ("commit", "domcontentloaded", "load", "networkidle"):
        return v
    return "domcontentloaded"


def _goto_timeout_ms(default_page_timeout: int) -> int:
    raw = (os.getenv("REGISTRO_CITA_GOTO_TIMEOUT_MS") or "").strip()
    if raw:
        try:
            ms = int(raw)
        except ValueError:
            ms = default_page_timeout
    else:
        ms = default_page_timeout
    return max(10_000, min(ms, 300_000))


def _log_goto_timeout_diagnosis(page_url: str) -> None:
    logger.error(
        "registro_cita: Page.goto agotó el tiempo. Causas frecuentes: (1) la web bloquea o "
        "prioriza mal el tráfico desde datacenters (IPs de Render/AWS); (2) TLS o red lenta; "
        "(3) domcontentloaded no llega por scripts/recursos colgados. Prueba en .env del worker: "
        "REGISTRO_CITA_GOTO_WAIT_UNTIL=commit, sube REGISTRO_CITA_GOTO_TIMEOUT_MS (p. ej. 180000), "
        "o ejecuta el worker desde una red residencial / VPN España / proxy saliente. URL=%s",
        page_url,
    )


def _page_goto_resilient(page: Page, url: str, wait_until: str, timeout_ms: int) -> None:
    """
    Navegación resiliente con reintentos y timeout extendido para producción.
    """
    logger.info(f"🌐 Navegando a: {url}")
    
    # Configurar reintentos para producción
    max_retries = 3 if os.getenv("RENDER", "").lower() in ("true", "1") else 2
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                logger.info(f"🔄 Reintento {attempt + 1}/{max_retries}...")
                wait_until = "commit"  # Más rápido en reintentos
                timeout = min(60000, timeout_ms)  # 1 minuto máximo en reintentos
            else:
                timeout = timeout_ms
                logger.info(f"⏱️ Timeout navegación: {timeout}ms ({timeout/1000} segundos)")
            
            page.goto(
                url,
                wait_until=wait_until,
                timeout=timeout,
            )
            logger.info("✅ Navegación completada")
            return
            
        except Exception as e:
            logger.warning(f"⚠️ Error navegación (intento {attempt + 1}): {e}")
            
            if attempt == max_retries - 1:
                # Último intento falló
                logger.error("❌ Todos los reintentos de navegación fallaron")
                raise e
            
            # Esperar antes de reintentar
            wait_time = (attempt + 1) * 5  # 5s, 10s, 15s
            logger.info(f"⏳ Esperando {wait_time}s antes de reintentar...")
            page.wait_for_timeout(wait_time * 1000)


def _resolve_form_root(page, nie_selector: str, timeout_ms: int) -> RootLike:
    """
    Muchos trámites @pre cargan el formulario dentro de un iframe.
    Si REGISTRO_CITA_IFRAME_SELECTOR está definido, se usa; si no, se prueba
    el documento principal y luego cada iframe.
    """
    iframe_css = (os.getenv("REGISTRO_CITA_IFRAME_SELECTOR") or "").strip()
    if iframe_css:
        fl = page.frame_locator(iframe_css)
        nie_loc = fl.locator(nie_selector).first
        _prepare_locator_attached(nie_loc, timeout_ms)
        logger.info("Formulario cita previa resuelto en iframe: %s", iframe_css)
        return fl

    deadline = time.monotonic() + timeout_ms / 1000.0
    last_err: Optional[Exception] = None
    while time.monotonic() < deadline:
        for frame in _iter_frames(page):
            loc = frame.locator(nie_selector).first
            try:
                chunk_ms = min(20000, int((deadline - time.monotonic()) * 1000))
                if chunk_ms < 500:
                    break
                _prepare_locator_attached(loc, chunk_ms)
                if frame == page.main_frame:
                    logger.debug("Formulario cita previa en documento principal (DOM attached)")
                    return page
                logger.info("Formulario cita previa encontrado en iframe (sin IFRAME_SELECTOR en .env)")
                return frame
            except Exception as e:
                last_err = e
                continue
        page.wait_for_timeout(500)

    msg = (
        f"No aparece el campo NIE ({nie_selector}) en el DOM (página ni iframes). "
        "Comprueba REGISTRO_CITA_URL (entrada por provincia o pantalla con #citadoForm). "
        "Si entras por lista de provincias, define REGISTRO_CITA_PROVINCIA y no uses "
        "REGISTRO_CITA_SKIP_WIZARD. Prueba REGISTRO_CITA_GOTO_WAIT_UNTIL=load o "
        "REGISTRO_CITA_IFRAME_SELECTOR si aplica."
    )
    logger.error(msg)
    raise TimeoutError(msg) from last_err


def _wait_dom_settled(page, timeout_ms: int) -> None:
    try:
        page.wait_for_load_state(
            "domcontentloaded",
            timeout=min(45000, max(5000, timeout_ms // 2)),
        )
    except Exception:
        page.wait_for_timeout(1200)


def _maybe_run_icpplus_wizard(page, timeout_ms: int, ff: bool) -> None:
    """
    Pasos previos en portal ICP: provincia → Aceptar → trámite → Aceptar → «Presentación sin Cl@ve».
    Si no hay pantalla de provincias (#divProvincias), no hace nada (URL directa al NIE).
    """
    if os.getenv("REGISTRO_CITA_SKIP_WIZARD", "").lower() in ("1", "true", "yes"):
        logger.info("REGISTRO_CITA_SKIP_WIZARD: se omite asistente provincia/trámite.")
        return

    prov_css = (
        os.getenv("REGISTRO_CITA_SEL_PROVINCIA") or "#divProvincias select#form"
    ).strip()
    detect_ms = int(os.getenv("REGISTRO_CITA_WIZARD_DETECT_MS", "12000") or "12000")
    prov_sel = page.locator(prov_css).first
    try:
        prov_sel.wait_for(state="attached", timeout=detect_ms)
    except Exception:
        logger.info(
            "No hay selector de provincia (%s); se asume entrada directa al formulario NIE.",
            prov_css,
        )
        return

    prov_val = (os.getenv("REGISTRO_CITA_PROVINCIA") or "").strip()
    if not prov_val:
        raise ValueError(
            "Hay pantalla de provincias: define REGISTRO_CITA_PROVINCIA con el atributo value "
            "de la opción (ej. Barcelona: /icpplustieb/citar?p=8&locale=es)."
        )

    logger.info("ICP: seleccionando provincia y tramitando pasos previos al formulario NIE.")
    _prepare_locator_attached(prov_sel, min(20000, timeout_ms))
    prov_sel.select_option(value=prov_val, force=ff)

    btn_ac = page.locator("input#btnAceptar").first
    _prepare_locator_attached(btn_ac, min(20000, timeout_ms))
    btn_ac.click(force=ff, timeout=timeout_ms)
    _wait_dom_settled(page, timeout_ms)

    tram_css = (
        os.getenv("REGISTRO_CITA_SEL_TRAMITE") or 'select[name="tramiteGrupo[0]"]'
    ).strip()
    tram_sel = page.locator(tram_css).first
    
    # Intentar esperar al selector del trámite con timeout más corto
    try:
        tram_sel.wait_for(state="attached", timeout=10000)  # 10 segundos máximo
        logger.info("✅ Selector de trámite encontrado")
    except Exception:
        logger.warning("🔍 Selector de trámite no encontrado - continuando sin wizard...")
        logger.info("✅ Saltando trámite - continuando al formulario directamente")
        return

    tram_val = (os.getenv("REGISTRO_CITA_TRAMITE") or "4010").strip()
    _prepare_locator_attached(tram_sel, min(20000, timeout_ms))
    tram_sel.select_option(value=tram_val, force=ff)

    btn_ac2 = page.locator("input#btnAceptar").first
    _prepare_locator_attached(btn_ac2, min(20000, timeout_ms))
    btn_ac2.click(force=ff, timeout=timeout_ms)
    _wait_dom_settled(page, timeout_ms)

    entrar = page.locator("#btnEntrar").first
    entrar.wait_for(state="attached", timeout=timeout_ms)
    _prepare_locator_attached(entrar, min(20000, timeout_ms))
    entrar.click(force=ff, timeout=timeout_ms)
    _wait_dom_settled(page, timeout_ms)
    logger.info("ICP: pasos previos completados; debería mostrarse el formulario de datos (NIE).")


def _get_by_role_click(root: RootLike, page, name: str, timeout_ms: int) -> None:
    """Intenta el botón en root (iframe) y si falla en la página completa."""
    ff = _fill_force()
    for candidate in (root, page):
        try:
            btn = candidate.get_by_role("button", name=name)
            try:
                btn.wait_for(state="visible", timeout=max(5000, timeout_ms // 3))
            except Exception:
                btn.wait_for(state="attached", timeout=max(5000, timeout_ms // 4))
            btn.click(timeout=timeout_ms, force=ff)
            return
        except Exception:
            continue
    raise TimeoutError(f"No se encontró el botón «{name}»")


def _diagnostic_email_enabled() -> bool:
    v = (os.getenv("REGISTRO_CITA_DIAGNOSTIC_EMAIL") or "true").strip().lower()
    return v not in ("0", "false", "no")


def _diagnostic_on_error_enabled() -> bool:
    return os.getenv("REGISTRO_CITA_DIAGNOSTIC_ON_ERROR", "").lower() in ("1", "true", "yes")


def _locator_count(page, selector: str) -> int:
    try:
        return page.locator(selector).count()
    except Exception:
        return -1


def _detect_perimeter_block(page) -> Optional[str]:
    """
    Detecta respuestas típicas de firewall / IPS / filtro web que sustituyen la página real.
    """
    try:
        title = (page.title() or "").lower()
    except Exception:
        title = ""

    title_hits = [
        ("intrusion prevention", "IPS/firewall: «Intrusion Prevention» (violación de política de salida)."),
        ("access has been denied", "Acceso denegado por proxy o filtro web."),
        ("url filter violation", "Filtro de URL del perímetro."),
        ("web filter violation", "Filtro web del perímetro."),
        ("access denied", "Acceso denegado (revisar política de salida a Internet)."),
        ("blocked by", "Petición bloqueada por política de seguridad."),
    ]
    for needle, msg in title_hits:
        if needle in title:
            return msg

    try:
        body_snip = (page.locator("body").inner_text(timeout=5000) or "").lower()[:3000]
    except Exception:
        body_snip = ""

    body_hits = [
        ("fortigate", "Página compatible con bloqueo FortiGate/Fortinet."),
        ("fortinet", "Página compatible con bloqueo Fortinet."),
        ("intrusion prevention", "Bloqueo IPS en el contenido devuelto."),
        ("palo alto networks", "Página compatible con bloqueo Palo Alto."),
        ("sophos", "Página compatible con filtro Sophos."),
        ("checkpoint", "Página compatible con bloqueo Check Point."),
        ("request was rejected", "Petición rechazada por el perímetro."),
        ("your request has been blocked", "Petición bloqueada explícitamente."),
    ]
    for needle, msg in body_hits:
        if needle in body_snip:
            return msg

    return None


def _format_page_diagnostic(url_env: str, page) -> str:
    """Texto legible: dónde ha quedado el navegador."""
    lines = [
        "=== Cita previa — diagnóstico de página ===",
        f"URL configurada (REGISTRO_CITA_URL): {url_env}",
    ]
    try:
        lines.append(f"URL actual (navegador): {page.url}")
    except Exception as ex:
        lines.append(f"URL actual: (error: {ex})")
    try:
        lines.append(f"Título: {page.title()}")
    except Exception as ex:
        lines.append(f"Título: (error: {ex})")

    checks = [
        ("#divProvincias select#form (provincia)", "#divProvincias select#form"),
        ("#citadoForm", "#citadoForm"),
        ("#txtIdCitado (NIE)", "#txtIdCitado"),
        ('select[name="tramiteGrupo[0]"] (trámite)', 'select[name="tramiteGrupo[0]"]'),
        ("#btnEntrar (sin Cl@ve)", "#btnEntrar"),
        ("main#mainWindow", "main#mainWindow"),
        ("#btnAceptar (wizard)", "input#btnAceptar"),
    ]
    lines.append("")
    lines.append("Elementos encontrados (conteo locators en documento principal):")
    for label, sel in checks:
        n = _locator_count(page, sel)
        lines.append(f"  - {label}: {n}")

    block = _detect_perimeter_block(page)
    if block:
        lines.append("")
        lines.append(">>> Posible bloqueo de red / firewall <<<")
        lines.append(block)
        lines.append(
            "Si todos los conteos son 0 y el título no es el de cita previa, "
            "el tráfico no está llegando al portal: contactar con IT (whitelist saliente)."
        )

    return "\n".join(lines)


def _send_diagnostic_mail(
    app,
    mail_to: list[str],
    subject_tag: str,
    body: str,
) -> None:
    sender = app.config.get("MAIL_DEFAULT_SENDER") or os.getenv("MAIL_DEFAULT_SENDER")
    if not sender:
        logger.warning("MAIL_DEFAULT_SENDER no configurado; no se envía diagnóstico.")
        return
    try:
        msg = EmailMessage(
            subject=f"Cita previa [diagnóstico] {subject_tag}",
            body=body,
            from_email=sender,
            to=mail_to,
        )
        msg.send()
        logger.info("Correo de diagnóstico cita previa enviado (%s).", subject_tag)
    except Exception:
        logger.exception("No se pudo enviar el correo de diagnóstico cita previa.")


def _send_execution_report_mail(
    app,
    mail_to: list[str],
    resultado: str,
    screenshots: list[str],
    execution_time: str,
    url: str,
    nie: str,
) -> None:
    """
    Envía un email con el reporte de cada ejecución del bot, incluyendo screenshots.
    """
    from datetime import datetime
    import os
    
    sender = app.config.get("MAIL_DEFAULT_SENDER") or os.getenv("MAIL_DEFAULT_SENDER")
    if not sender:
        logger.warning("MAIL_DEFAULT_SENDER no configurado; no se envía reporte de ejecución.")
        return
    
    try:
        # Crear el cuerpo del email
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        body = f"""
🤖 REPORTE DE EJECUCIÓN - BOT DE CITAS
====================================

📅 Fecha y hora: {timestamp}
⏱️ Duración: {execution_time}
🆔 NIE utilizado: {nie}
🌐 URL consultada: {url}

📊 RESULTADO: {resultado}

📸 Screenshots adjuntos: {len(screenshots)}
"""
        
        # Añadir detalles de los screenshots
        if screenshots:
            body += "\n📋 Detalles de capturas:\n"
            for i, screenshot in enumerate(screenshots, 1):
                if os.path.exists(screenshot):
                    body += f"   {i}. {screenshot} ✅\n"
                else:
                    body += f"   {i}. {screenshot} ❌ (no encontrado)\n"
        
        body += f"""

🔧 Configuración del bot:
- Ambiente: {'Producción (Render)' if os.getenv('RENDER', '').lower() in ('true', '1') else 'Desarrollo'}
- Headless: {'Sí' if os.getenv('REGISTRO_CITA_HEADLESS', 'false').lower() in ('true', '1') else 'No'}
- Stealth: {'Disponible' if os.getenv('PLAYWRIGHT_STEALTH_AVAILABLE', '').lower() in ('true', '1') else 'No disponible'}

📌 Notas:
- Este email se envía automáticamente en cada ejecución
- Los screenshots muestran el estado del proceso
- Revisa las capturas para verificar el funcionamiento

🚀 Bot de Citas - Sistema Automatizado
"""
        
        # Crear el mensaje con adjuntos
        from django.core.mail import EmailMessage
        
        msg = EmailMessage(
            subject=f"🤖 Bot Citas - Reporte Ejecución: {resultado}",
            body=body,
            from_email=sender,
            to=mail_to,
        )
        
        # Adjuntar screenshots si existen
        attachments_added = 0
        for screenshot_path in screenshots:
            if os.path.exists(screenshot_path):
                try:
                    with open(screenshot_path, 'rb') as f:
                        msg.attach(f"screenshot_{os.path.basename(screenshot_path)}", f.read(), 'image/png')
                        attachments_added += 1
                        logger.info(f"📎 Screenshot adjuntado: {screenshot_path}")
                except Exception as e:
                    logger.warning(f"⚠️ Error adjuntando screenshot {screenshot_path}: {e}")
        
        # Enviar el email
        msg.send()
        logger.info(f"📧 Reporte de ejecución enviado: {resultado} ({attachments_added} screenshots adjuntados)")
        
    except Exception as e:
        logger.exception(f"❌ Error enviando reporte de ejecución: {e}")


def _send_aviso_mail(app, url: str, mail_to: list[str]) -> None:
    sender = app.config.get("MAIL_DEFAULT_SENDER") or os.getenv("MAIL_DEFAULT_SENDER")
    if not sender:
        logger.warning("MAIL_DEFAULT_SENDER no configurado; no se envía el aviso.")
        return
    msg = EmailMessage(
        subject="Cita previa: hay citas disponibles",
        body=(
            "Se ha detectado que hay citas disponibles en el flujo configurado "
            f"(comprobación automática).\n\nURL consultada:\n{url}\n\n"
            "Entra en la web y completa la reserva manualmente si aún lo necesitas."
        ),
        from_email=sender,
        to=mail_to,
    )
    msg.send()


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.utils.tasks.registro_cita.registro_cita",
    time_limit=600,
    soft_time_limit=540,
    cache_result=False,
)
def registro_cita(self) -> bool:
    """
    Tarea principal que automatiza el registro de cita previa.
    Ahora envía un reporte de ejecución con screenshots en cada ejecución.
    """
    from datetime import datetime
    import time
    
    # Tiempo de inicio para medir duración
    start_time = time.time()
    execution_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    app = self.app
    url = os.getenv("REGISTRO_CITA_URL")
    if not url:
        logger.error("REGISTRO_CITA_URL no configurada")
        return False

    mail_to = [email.strip() for email in os.getenv("REGISTRO_CITA_MAIL_TO", "").split(",") if email.strip()]
    if not mail_to:
        logger.warning("REGISTRO_CITA_MAIL_TO no configurado; no se enviarán correos.")
    
    nie = os.getenv("REGISTRO_CITA_NIE")
    nombre = os.getenv("REGISTRO_CITA_NOMBRE")
    pais = os.getenv("REGISTRO_CITA_PAIS")
    
    # Lista para almacenar paths de screenshots
    screenshots_taken = []
    
    logger.info("🚀 INICIO DE TAREA registro_cita - Bot de Citas")
    logger.info("📋 Configuración:")
    logger.info(f"   📍 Provincia: No configurada")
    logger.info(f"   🆔 NIE: {nie}")
    logger.info(f"   👤 Nombre: {nombre}")
    logger.info(f"   🌍 País: No configurada")
    logger.info(f"   📧 Email: {', '.join(mail_to) if mail_to else 'No configurado'}")
    logger.info(f"   🧙 Stealth: {STEALTH_AVAILABLE}")
    logger.info(f"   👁️ Headless: {os.getenv('REGISTRO_CITA_HEADLESS', 'true')}")
    logger.info(f" 🌐 URL objetivo: {url}")
    logger.info(f" 📧 Destinatarios: {mail_to}")
    logger.info(f" 🆔 NIE a usar: {nie}")
    logger.info(f" 👤 Nombre a usar: {nombre}")
    logger.info(f" 🌍 País a usar: {pais}")

    # Función auxiliar para tomar screenshots con timestamp
    def take_screenshot(page, description):
        """Toma un screenshot con timestamp y lo añade a la lista"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bot_cita_{execution_timestamp}_{description.replace(' ', '_').lower()}.png"
            page.screenshot(path=filename, full_page=True)
            screenshots_taken.append(filename)
            logger.info(f"📸 Screenshot guardado: {filename}")
            return filename
        except Exception as e:
            logger.warning(f"⚠️ Error tomando screenshot '{description}': {e}")
            return None

    state = _load_state()
    hay_citas = False
    sin_citas = False
    page = None
    diag_sent_before_nie = False

    try:
        with sync_playwright() as p:
            # Detectar si estamos en producción (Render) o desarrollo
            is_production = (
                os.getenv("RENDER", "").lower() in ("true", "1") or 
                os.getenv("ENVIRONMENT", "").lower() in ("production", "prod") or
                os.getenv("PYTHONUNBUFFERED", "") == "1"  # Indicador de Render
            )
            
            # Forzar headless en producción SIEMPRE
            if is_production:
                headless = True
                logger.info("🏭 Producción detectada - Forzando modo headless")
            else:
                headless = os.getenv("REGISTRO_CITA_HEADLESS", "false").lower() in ("true", "1")
                logger.info(f"👁️ Modo headless: {headless}")
            
            # Mostrar configuración
            logger.info(f"🌍 Ambiente: {'Producción' if is_production else 'Desarrollo'}")
            logger.info(f"🧙 Stealth: {STEALTH_AVAILABLE}")
            
            # Args comunes para Linux/Producción
            launch_args = [
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--disable-background-networking",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-client-side-phishing-detection",
                "--disable-component-extensions-with-background-pages",
                "--disable-default-apps",
                "--disable-extensions",
                "--disable-sync",
                "--disable-translate",
                "--metrics-recording-only",
                "--no-first-run",
                "--safebrowsing-disable-auto-update",
                "--password-store=basic",
                "--use-mock-keychain",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--disable-setuid-sandbox",
                "--disable-features=AudioServiceOutOfProcess",  # Reducir errores
                "--disable-features=AudioContext",  # Reducir errores
                "--disable-features=WebRTC",  # Reducir errores
            ]
            
            # EN PRODUCCIÓN: Siempre usar navegador normal sin perfil
            if is_production:
                logger.info("🟡 Producción - Usando Playwright normal (sin perfil)")
                browser = p.chromium.launch(
                    headless=True,  # Siempre headless en producción
                    args=launch_args
                )
                
                # Crear contexto realista
                context = browser.new_context(
                    locale="es-ES",
                    timezone_id="Europe/Madrid",
                    user_agent=_get_realistic_user_agent(),
                    viewport={"width": 1366, "height": 768},
                    device_scale_factor=1.0,
                    is_mobile=False,
                    has_touch=False,
                    java_script_enabled=True,
                    extra_http_headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                        "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3",
                        "Accept-Encoding": "gzip, deflate, br",
                        "DNT": "1",
                        "Connection": "keep-alive",
                        "Upgrade-Insecure-Requests": "1"
                    },
                    ignore_https_errors=os.getenv("REGISTRO_CITA_IGNORE_HTTPS_ERRORS", "").lower() in ("1", "true", "yes")
                )
                page = context.new_page()
                
                # Timeout extendido para producción
                timeout_ms = max(180000, int(os.getenv("REGISTRO_CITA_TIMEOUT_MS", "180000")))  # Mínimo 3 minutos
                page.set_default_timeout(timeout_ms)
                goto_timeout = timeout_ms
                
                logger.info(f"⏱️ Timeout producción: {timeout_ms}ms ({timeout_ms/1000/60} minutos)")
                
            else:
                # DESARROLLO: Usar navegador con perfil si está disponible
                if STEALTH_AVAILABLE:
                    logger.info("🟢 Desarrollo - Usando navegador REAL con sesión de Chrome")
                    bot_profile_dir = os.getenv("CHROME_PROFILE_DIR", os.path.expanduser("~/AppData/Local/Google/Chrome/User Data/BotProfile"))
                    
                    browser = p.chromium.launch_persistent_context(
                        user_data_dir=bot_profile_dir,
                        headless=headless,
                        args=launch_args
                    )
                    page = browser.new_page()
                else:
                    logger.info("🟡 Desarrollo - Usando Playwright normal (sin sesión real)")
                    browser = p.chromium.launch(
                        headless=headless,
                        args=launch_args
                    )
                    
                    context = browser.new_context(
                        locale="es-ES",
                        timezone_id="Europe/Madrid",
                        user_agent=_get_realistic_user_agent(),
                        viewport={"width": 1366, "height": 768},
                        device_scale_factor=1.0,
                        is_mobile=False,
                        has_touch=False,
                        java_script_enabled=True,
                        extra_http_headers={
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                            "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3",
                            "Accept-Encoding": "gzip, deflate, br",
                            "DNT": "1",
                            "Connection": "keep-alive",
                            "Upgrade-Insecure-Requests": "1"
                        },
                        ignore_https_errors=os.getenv("REGISTRO_CITA_IGNORE_HTTPS_ERRORS", "").lower() in ("1", "true", "yes")
                    )
                    page = context.new_page()
                
                # Timeout normal para desarrollo
                timeout_ms = int(os.getenv("REGISTRO_CITA_TIMEOUT_MS", "90000"))
                page.set_default_timeout(timeout_ms)
                goto_timeout = _goto_timeout_ms(timeout_ms)
            
            # Aplicar técnicas de stealth
            _apply_stealth(page)
            
            # Simular comportamiento humano inicial
            _human_delay(2, 4)
            _simulate_mouse_movement(page)
            
            # Tomar screenshot inicial
            take_screenshot(page, "inicio_navegacion")
            
            # Navegación con espera realista (CLAVE)
            _human_delay(3, 6)  # Espera más larga para evitar detección
            logger.info(f"🌐 Navegando a: {url}")
            _page_goto_resilient(page, url, _goto_wait_until(), goto_timeout)
            logger.info("✅ Navegación completada")
            
            # Tomar screenshot después de navegación
            take_screenshot(page, "pagina_cargada")
            
            # Simular comportamiento humano post-navegación
            _human_delay(3, 5)
            _simulate_mouse_movement(page)
            
            # 👈 ESPERA REAL CLAVE - Dejar que cargue completamente
            logger.info("⏳ Espera real de 10 segundos para carga completa...")
            time.sleep(10)  # Aumentado a 10 segundos
            logger.info("✅ Espera de carga completada")
            
            # Espera adicional aleatoria para simular comportamiento humano
            espera_extra = random.randint(5, 15)
            logger.info(f"🕰️ Espera adicional aleatoria: {espera_extra} segundos")
            time.sleep(espera_extra)
            
            _human_delay(3, 6)  # Espera más larga
            _simulate_mouse_movement(page)
            
            # 🧪 DEBUG: Screenshot para ver qué página carga realmente
            take_screenshot(page, "antes_de_formulario")
            
            # 👈 ESPERA REAL CLAVE - Dejar que cargue completamente
            logger.info("⏳ Espera real de 10 segundos para carga completa...")
            time.sleep(10)  # Aumentado a 10 segundos
            logger.info("✅ Espera de carga completada")
            
            # Espera adicional aleatoria para simular comportamiento humano
            espera_extra = random.randint(5, 15)
            logger.info(f"🕰️ Espera adicional aleatoria: {espera_extra} segundos")
            time.sleep(espera_extra)
            
            _human_delay(3, 6)  # Espera más larga
            _simulate_mouse_movement(page)
            
            # Tomar screenshot después de esperar
            take_screenshot(page, "despues_de_espera")
            
            # Espera extra configurada
            extra_wait = int(os.getenv("REGISTRO_CITA_POST_GOTO_MS", "0") or "0")
            if extra_wait > 0:
                page.wait_for_timeout(min(extra_wait, 60000))

            perimeter = _detect_perimeter_block(page)
            if perimeter:
                logger.error(
                    "registro_cita: el servidor no llega al portal de citas (bloqueo de red). %s URL=%s",
                    perimeter,
                    page.url,
                )
                if _diagnostic_email_enabled():
                    body = _format_page_diagnostic(url, page)
                    _send_diagnostic_mail(
                        app,
                        mail_to,
                        "BLOQUEO firewall/IPS — revisar IT",
                        body,
                    )
                    diag_sent_before_nie = True
                browser.close()
                return

            logger.info("🔍 Verificando bloqueos de red... OK")
            logger.info("🎯 Ejecutando wizard de trámites...")
            ff = _fill_force()
            _maybe_run_icpplus_wizard(page, timeout_ms, ff)
            logger.info("✅ Wizard completado")

            ready_raw = os.getenv("REGISTRO_CITA_PAGE_READY_SELECTOR")
            ready_sel = (
                "#citadoForm"
                if ready_raw is None
                else ready_raw.strip()
            )
            if ready_sel and ready_sel.lower() not in ("none", "false", "-"):
                    try:
                        page.wait_for_selector(
                            ready_sel,
                            state="attached",
                            timeout=min(45000, timeout_ms),
                        )
                        logger.info(f"✅ Selector de página lista encontrado: {ready_sel}")
                    except Exception:
                        logger.warning(
                            "No apareció a tiempo el selector de página lista (%s); se sigue igualmente.",
                            ready_sel,
                        )

            sel_nie = (os.getenv("REGISTRO_CITA_SEL_NIE") or "#txtIdCitado").strip()
            sel_nom = (os.getenv("REGISTRO_CITA_SEL_NOMBRE") or "#txtDesCitado").strip()
            sel_pais = (os.getenv("REGISTRO_CITA_SEL_PAIS") or "#txtPaisNac").strip()

            if _diagnostic_email_enabled():
                body = _format_page_diagnostic(url, page)
                _send_diagnostic_mail(
                    app,
                    mail_to,
                    "antes del formulario NIE",
                    body,
                )
                diag_sent_before_nie = True

            logger.info("🔍 Buscando formulario de NIE...")
            root = _resolve_form_root(page, sel_nie, timeout_ms)
            logger.info("✅ Formulario encontrado")
            
            # Tomar screenshot del formulario
            take_screenshot(page, "formulario_encontrado")
            
            # Simular comportamiento humano al rellenar formulario
            _human_delay(1, 3)
            _simulate_mouse_movement(page)
            
            logger.info("📝 Rellenando formulario...")
            # Rellenar NIE con typing humano
            nie_input = root.locator(sel_nie).first
            nie_input.click()
            _human_delay(0.5, 1.5)
            nie_input.fill(nie, force=ff)
            logger.info(f"✅ NIE rellenado: {nie}")
            _human_delay(1, 2)
            
            # Tomar screenshot después de rellenar NIE
            take_screenshot(page, "nie_rellenado")
            
            # Rellenar nombre con typing humano
            nom_input = root.locator(sel_nom).first
            _simulate_mouse_movement(page)
            nom_input.click()
            _human_delay(0.5, 1.5)
            nom_input.fill(nombre, force=ff)
            logger.info(f"✅ Nombre rellenado: {nombre}")
            _human_delay(1, 2)
            
            # Tomar screenshot después de rellenar nombre
            take_screenshot(page, "nombre_rellenado")
            
            # Seleccionar país
            pais_input = root.locator(sel_pais).first
            _simulate_mouse_movement(page)
            pais_input.click()
            _human_delay(0.5, 1.5)
                pais_input.select_option(pais, force=ff)
            logger.info(f"✅ País seleccionado: {pais}")
            _human_delay(1, 2)

            # Tomar screenshot del formulario completo
            take_screenshot(page, "formulario_completo")

            logger.info("🖱️ Haciendo clic en botones...")
            # Buscar y hacer clic en botón "Solicitar Cita" primero
            _simulate_mouse_movement(page)
            _human_delay(1, 3)
            try:
                logger.info("🔘 Buscando botón 'Solicitar Cita'...")
                # Intentar diferentes selectores para "Solicitar Cita"
                solicitando_selectors = [
                    'button:has-text("Solicitar Cita")',
                    'input[value="Solicitar Cita"]',
                    'a:has-text("Solicitar Cita")',
                    '[role="button"]:has-text("Solicitar Cita")',
                    '#btnSolicitar',
                    '.btn-solicitar'
                ]
                    
                    boton_encontrado = False
                    for selector in solicitando_selectors:
                        try:
                            element = page.query_selector(selector)
                            if element:
                                element.click()
                                logger.info(f"✅ Botón 'Solicitar Cita' clicado con selector: {selector}")
                                boton_encontrado = True
                                break
                        except Exception:
                            continue
                    
                    if not boton_encontrado:
                        logger.warning("🔍 Botón 'Solicitar Cita' no encontrado con ningún selector")
                    
                    _human_delay(2, 4)
                except Exception as e:
                    logger.warning(f"❌ Error buscando 'Solicitar Cita': {e}")
                
                # Buscar y hacer clic en botón "Aceptar" (btnEnviar)
                _simulate_mouse_movement(page)
                _human_delay(1, 3)
                try:
                    logger.info("🔘 Buscando botón 'Aceptar' (btnEnviar)...")
                    # Intentar diferentes selectores para "Aceptar"
                    aceptar_selectors = [
                        '#btnEnviar',
                        'input#btnEnviar[type="button"]',
                        'input[value="Aceptar"]',
                        'button:has-text("Aceptar")',
                        '.mf-button.primary',
                        'input.mf-button.primary'
                    ]
                    
                    boton_aceptar_encontrado = False
                    for selector in aceptar_selectors:
                        try:
                            element = page.query_selector(selector)
                            if element:
                                element.click()
                                logger.info(f"✅ Botón 'Aceptar' clicado con selector: {selector}")
                                boton_aceptar_encontrado = True
                                break
                        except Exception:
                            continue
                    
                    if not boton_aceptar_encontrado:
                        logger.warning("🔍 Botón 'Aceptar' no encontrado con ningún selector")
                    
                    _human_delay(2, 4)
                except Exception as e:
                    logger.warning(f"❌ Error buscando 'Aceptar': {e}")
                
                # Si no se encontró ningún botón, intentar hacer clic por rol
                if not boton_encontrado and not boton_aceptar_encontrado:
                    logger.info("� Intentando clic por rol como fallback...")
                    try:
                        _get_by_role_click(root, page, "Aceptar", timeout_ms)
                        logger.info("✅ Botón 'Aceptar' clicado por rol")
                    except Exception:
                        try:
                            _get_by_role_click(root, page, "Solicitar Cita", timeout_ms)
                            logger.info("✅ Botón 'Solicitar Cita' clicado por rol")
                        except Exception:
                            logger.warning("🔍 No se pudo hacer clic en ningún botón")
                            logger.info("✅ Proceso completado hasta donde fue posible")

                logger.info("🔍 Detectando resultados...")
                try:
                    hay_citas, sin_citas = _detect_result(page)
                    logger.info(f"📊 Resultado detección: hay_citas={hay_citas}, sin_citas={sin_citas}")
                except Exception as e:
                    logger.warning(f"❌ Error en detección de resultados: {e}")
                    logger.info("🤷 RESULTADO: Error en detección - asumiendo que no hay citas")
                    hay_citas, sin_citas = False, True
                
                # 🧪 DEBUG: Screenshot final del resultado
                try:
                    final_screenshot_path = "debug_cita_bot_final.png"
                    page.screenshot(path=final_screenshot_path, full_page=True)
                    logger.info(f"📸 Screenshot final guardado en: {final_screenshot_path}")
                except Exception as e:
                    logger.warning(f"No se pudo guardar screenshot final: {e}")
                
                # Cerrar browser de forma segura
                if use_real_browser:
                    logger.info("🟢 Cerrando navegador REAL (puede que Chrome siga abierto)")
                    # No cerrar Chrome persistente para que el usuario pueda verlo
                    # browser.close()  # Comentado para mantener Chrome abierto
                else:
                    logger.info("🟡 Cerrando navegador Playwright")
                    browser.close()
        except Exception as e:
            logger.exception("Error en la automatización de registro cita (Playwright).")
            
            # Enviar reporte de ejecución con error
            execution_time = f"{time.time() - start_time:.1f}s"
            try:
                _send_execution_report_mail(
                    app, mail_to, f"ERROR: {type(e).__name__}", screenshots_taken, 
                    execution_time, url, nie or "No configurado"
                )
            except Exception as report_error:
                logger.warning(f"⚠️ Error enviando reporte de error: {report_error}")
            
            if _diagnostic_on_error_enabled() and page is not None:
                try:
                    if diag_sent_before_nie:
                        try:
                            tit = page.title()
                        except Exception:
                            tit = "(no disponible)"
                        try:
                            purl = page.url
                        except Exception:
                            purl = "(no disponible)"
                        short = (
                            f"Fallo después del correo de diagnóstico previo.\n\n"
                            f"{type(e).__name__}: {e}\n\n"
                            f"URL actual: {purl}\n"
                            f"Título: {tit}"
                        )
                        _send_diagnostic_mail(
                            app,
                            mail_to,
                            "error (resumen)",
                            short,
                        )
                    else:
                        body = _format_page_diagnostic(url, page)
                        body += f"\n\n--- Excepción ---\n{type(e).__name__}: {e}"
                        _send_diagnostic_mail(
                            app,
                            mail_to,
                            "error",
                            body,
                        )
                except Exception:
                    logger.exception("Diagnóstico tras error: no se pudo capturar/enviar.")
            err = str(e).lower()
            if "libgbm" in err or "shared libraries" in err or "error while loading shared libraries" in err:
                logger.error(
                    "Chromium de Playwright no arranca: faltan librerías del sistema. "
                    "En Ubuntu/Debian (usuario con sudo): sudo apt install -y libgbm1 "
                    "o, desde el venv con permisos adecuados: playwright install-deps chromium"
                )
            if "executable doesn't exist" in err or "playwright install" in err:
                logger.error(
                    "Playwright: faltan binarios del navegador. En build: "
                    "PLAYWRIGHT_BROWSERS_PATH=0 pip install -r requirements.txt && playwright install chromium; "
                    "en runtime: env PLAYWRIGHT_BROWSERS_PATH=0 (Render/workers)."
                )
            raise

        if sin_citas:
            logger.info("📋 RESULTADO: Sin citas disponibles")
            logger.info("🔄 No hay citas - continuando monitoreo...")
            state["already_notified"] = False
            _save_state(state)
            
            # Enviar reporte de ejecución
            execution_time = f"{time.time() - start_time:.1f}s"
            try:
                _send_execution_report_mail(
                    app, mail_to, "SIN CITAS", screenshots_taken, 
                    execution_time, url, nie or "No configurado"
                )
            except Exception as e:
                logger.warning(f"⚠️ Error enviando reporte: {e}")
            
            logger.info("Cita previa: sin citas disponibles (continuando monitoreo).")
            return False

        if hay_citas:
            logger.info("🎉 RESULTADO: ¡CITAS DISPONIBLES!")
            if not state.get("already_notified"):
                logger.info("📧 Enviando email de aviso de citas disponibles...")
                try:
                    _send_aviso_mail(app, url, mail_to)
                    logger.info("✅ Email de aviso enviado correctamente")
                except Exception:
                    logger.exception("Error al enviar correo de aviso de cita previa.")
                    return
                state["already_notified"] = True
                _save_state(state)
                logger.info("Cita previa: aviso por correo enviado (citas detectadas).")
            else:
                logger.debug("Cita previa: citas disponibles; aviso ya enviado previamente.")
            
            # Enviar reporte de ejecución
            execution_time = f"{time.time() - start_time:.1f}s"
            try:
                _send_execution_report_mail(
                    app, mail_to, "CITAS DISPONIBLES", screenshots_taken, 
                    execution_time, url, nie or "No configurado"
                )
            except Exception as e:
                logger.warning(f"⚠️ Error enviando reporte: {e}")
            
            return True

        logger.warning(
            "Cita previa: resultado ambiguo (ni selector de sede ni mensaje sin citas)."
        )
        logger.info("🤷 RESULTADO: Ambiguo - no se pudo determinar si hay citas o no")
        
        # Enviar reporte de ejecución
        execution_time = f"{time.time() - start_time:.1f}s"
        try:
            _send_execution_report_mail(
                app, mail_to, "RESULTADO AMBIGUO", screenshots_taken, 
                execution_time, url, nie or "No configurado"
            )
        except Exception as e:
            logger.warning(f"⚠️ Error enviando reporte: {e}")
        
        return False
