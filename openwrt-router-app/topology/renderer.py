from __future__ import annotations

import html

import streamlit as st
import streamlit.components.v1 as components

from core.branding import STATE_COLORS, STATE_TEXT_ON_LIGHT_COLORS, TEXT_COLOR
from diagnostics.enums import DiagnosticState
from topology.models import TopologyGraph

# Reuses the single shared state-color source (core/branding.py) instead of
# keeping a second copy of the same palette in sync by hand.
_STATE_COLORS: dict[DiagnosticState, str] = {
    DiagnosticState(state): color for state, color in STATE_COLORS.items()
}
_STATE_TEXT_ON_LIGHT: dict[DiagnosticState, str] = {
    DiagnosticState(state): color for state, color in STATE_TEXT_ON_LIGHT_COLORS.items()
}

# Single consistent monochrome line-icon style (stroke=currentColor picks up
# the node's white text color) instead of mismatched colorful emoji.
_NODE_ICONS = {
    "dev_machine": (
        '<svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<rect x="2" y="4" width="20" height="14" rx="2"/>'
        '<line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="18" x2="12" y2="21"/>'
        "</svg>"
    ),
    "openwrt_router": (
        '<svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<rect x="2" y="14" width="20" height="7" rx="2"/>'
        '<line x1="6" y1="17.5" x2="6.01" y2="17.5"/><line x1="10" y1="17.5" x2="10.01" y2="17.5"/>'
        '<path d="M12 10a4 4 0 0 1 4 4"/><path d="M12 6a8 8 0 0 1 8 8"/>'
        "</svg>"
    ),
}

_TEMPLATE = """
<div class="idaf-topo">
  <style>
    .idaf-topo {{
      font-family: "IBM Plex Sans", -apple-system, "Segoe UI", Arial, sans-serif;
      display: flex;
      flex-direction: column;
      gap: 14px;
      color: {text_color};
    }}
    .idaf-topo * {{ box-sizing: border-box; }}
    .idaf-row {{
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0;
      padding: 24px 8px 8px;
    }}
    .idaf-node {{
      width: 190px;
      border: none;
      border-radius: 12px;
      padding: 16px 14px;
      text-align: center;
      color: {text_color};
      font: inherit;
      display: block;
      cursor: pointer;
      box-shadow: 0 4px 14px rgba(0,0,0,0.18);
      transition: transform 0.15s ease, box-shadow 0.15s ease;
      position: relative;
      flex-shrink: 0;
    }}
    .idaf-node:hover {{
      transform: translateY(-4px);
      box-shadow: 0 8px 20px rgba(0,0,0,0.28);
    }}
    .idaf-node:focus-visible {{
      outline: 3px solid {text_color};
      outline-offset: 2px;
    }}
    .idaf-node .icon {{ display: flex; justify-content: center; line-height: 1; }}
    .idaf-node .label {{ font-weight: 700; margin-top: 6px; font-size: 14px; }}
    .idaf-node .pill {{
      display: inline-block;
      margin-top: 6px;
      padding: 2px 10px;
      border-radius: 8px;
      font-size: 11px;
      font-weight: 700;
      color: {text_color};
      background: rgba(255,255,255,0.85);
    }}
    .idaf-node.pulse {{ animation: idaf-pulse 1.6s ease-in-out infinite; }}
    @keyframes idaf-pulse {{
      0% {{ box-shadow: 0 4px 14px rgba(0,0,0,0.18), 0 0 0 0 rgba(231,76,60,0.55); }}
      70% {{ box-shadow: 0 4px 14px rgba(0,0,0,0.18), 0 0 0 14px rgba(231,76,60,0); }}
      100% {{ box-shadow: 0 4px 14px rgba(0,0,0,0.18), 0 0 0 0 rgba(231,76,60,0); }}
    }}
    .idaf-link {{
      position: relative;
      flex-grow: 1;
      height: 4px;
      min-width: 60px;
      max-width: 220px;
      margin: 0 -2px;
      background: repeating-linear-gradient(
        90deg, {link_color} 0 10px, transparent 10px 18px
      );
    }}
    .idaf-link .dot {{
      position: absolute;
      top: -4px;
      left: 0;
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: {link_color};
      box-shadow: 0 0 6px {link_color};
      animation: idaf-flow 2.2s linear infinite;
    }}
    @keyframes idaf-flow {{
      0% {{ left: 0%; opacity: 0; }}
      10% {{ opacity: 1; }}
      90% {{ opacity: 1; }}
      100% {{ left: calc(100% - 12px); opacity: 0; }}
    }}
    .idaf-link .tag {{
      position: absolute;
      top: -22px;
      left: 50%;
      transform: translateX(-50%);
      font-size: 11px;
      font-weight: 700;
      color: {link_text_color};
      background: white;
      padding: 0 6px;
      white-space: nowrap;
    }}
    .idaf-detail {{
      display: none;
      border: 1px solid #e2e2e2;
      border-radius: 12px;
      padding: 10px 14px;
      font-size: 13px;
      background: #fafafa;
    }}
    .idaf-detail.open {{ display: block; }}
    .idaf-detail b {{ display: inline-block; min-width: 110px; }}
    .idaf-hint {{
      text-align: center;
      font-size: 12px;
      color: #767676;
    }}

    /* Below ~480px the two 190px nodes plus link no longer fit side by
       side without horizontal overflow; stack them and turn the link
       into a vertical connector instead of just shrinking the nodes. */
    @media (max-width: 480px) {{
      .idaf-row {{
        flex-direction: column;
        padding: 16px 8px 8px;
      }}
      .idaf-node {{
        width: 100%;
        max-width: 260px;
      }}
      .idaf-link {{
        flex-grow: 0;
        width: 4px;
        height: 56px;
        min-width: 0;
        max-width: none;
        margin: -2px 0;
        background: repeating-linear-gradient(
          180deg, {link_color} 0 10px, transparent 10px 18px
        );
      }}
      .idaf-link .dot {{
        top: 0;
        left: -4px;
        animation-name: idaf-flow-vertical;
      }}
      .idaf-link .tag {{
        top: 50%;
        left: -8px;
        transform: translate(-100%, -50%);
      }}
      @keyframes idaf-flow-vertical {{
        0% {{ top: 0%; opacity: 0; }}
        10% {{ opacity: 1; }}
        90% {{ opacity: 1; }}
        100% {{ top: calc(100% - 12px); opacity: 0; }}
      }}
    }}

    /* The pulse and flowing dot are continuous, auto-starting motion with
       no built-in pause control (WCAG 2.2.2). Keep the signal they carry
       (critical/unreachable urgency, link direction) but drop the motion. */
    @media (prefers-reduced-motion: reduce) {{
      .idaf-node, .idaf-node.pulse {{
        animation: none;
        transition: none;
      }}
      .idaf-node.pulse {{
        box-shadow: 0 4px 14px rgba(0,0,0,0.18), 0 0 0 4px rgba(231,76,60,0.65);
      }}
      .idaf-link .dot {{
        animation: none;
        opacity: 1;
        left: calc(50% - 6px);
        top: -4px;
      }}
    }}
  </style>

  <div class="idaf-row">
    {pc_node}
    <div class="idaf-link">
      <span class="tag">{link_type}</span>
      <div class="dot"></div>
    </div>
    {router_node}
  </div>
  <div class="idaf-hint">Haz clic en un nodo para ver sus detalles.</div>

  {details}

  <script>
    function idafToggle(id, trigger) {{
      var el = document.getElementById(id);
      var isOpen = el.classList.contains('open');
      document.querySelectorAll('.idaf-detail').forEach(function(d) {{ d.classList.remove('open'); }});
      document.querySelectorAll('.idaf-node').forEach(function(n) {{ n.setAttribute('aria-expanded', 'false'); }});
      if (!isOpen) {{
        el.classList.add('open');
        if (trigger) {{ trigger.setAttribute('aria-expanded', 'true'); }}
      }}
    }}
  </script>
</div>
"""


def _node_html(node, node_id: str, color: str, pulse: bool) -> str:
    icon = _NODE_ICONS.get(node.type, _NODE_ICONS["dev_machine"])
    label = html.escape(node.label)
    pulse_class = " pulse" if pulse else ""
    # A real <button>, not a clickable <div>, so the only interactive
    # element in this custom component is reachable and operable via
    # keyboard (Tab + Enter/Space) and announced correctly by screen readers.
    return (
        f'<button type="button" class="idaf-node{pulse_class}" style="background:{color};" '
        f'onclick="idafToggle(\'{node_id}\', this)" aria-expanded="false" aria-controls="{node_id}">'
        f'<div class="icon">{icon}</div>'
        f'<div class="label">{label}</div>'
        f'<div class="pill">{node.state.value}</div>'
        f"</button>"
    )


def _detail_html(node, node_id: str) -> str:
    metadata_rows = "".join(
        f"<div><b>{html.escape(str(k))}:</b> {html.escape(str(v))}</div>" for k, v in node.metadata.items()
    )
    return (
        f'<div class="idaf-detail" id="{node_id}">'
        f"<div><b>ID:</b> {html.escape(node.id)}</div>"
        f"<div><b>Tipo:</b> {html.escape(node.type)}</div>"
        f"<div><b>Estado:</b> {node.state.value}</div>"
        f"{metadata_rows}"
        f"</div>"
    )


def render_topology(graph: TopologyGraph) -> None:
    """Render a small interactive PC<->router topology diagram.

    Self-contained HTML/CSS/JS via `streamlit.components.v1.html`: no new
    pip dependency, no external CDN. Hovering lifts a node, clicking a node
    toggles an inline detail panel, and the link animates a moving dot
    whose color mirrors the router's current diagnostic state.
    """
    if len(graph.nodes) < 2 or not graph.links:
        st.info("No hay suficiente información de topología para mostrar.")
        return

    pc_node, router_node = graph.nodes[0], graph.nodes[1]
    link = graph.links[0]

    pc_color = _STATE_COLORS.get(pc_node.state, "#95a5a6")
    router_color = _STATE_COLORS.get(router_node.state, "#95a5a6")
    link_color = _STATE_COLORS.get(link.state, "#95a5a6")
    # The link tag is colored text directly on a white background, so it
    # needs the darker on-light variant, not the vivid state color used for
    # node fills (the vivid values fail WCAG AA as text on white).
    link_text_color = _STATE_TEXT_ON_LIGHT.get(link.state, "#5d6d7e")
    router_pulse = router_node.state in (DiagnosticState.CRITICAL, DiagnosticState.UNREACHABLE)

    body = _TEMPLATE.format(
        pc_node=_node_html(pc_node, "idaf-detail-pc", pc_color, pulse=False),
        router_node=_node_html(router_node, "idaf-detail-router", router_color, pulse=router_pulse),
        text_color=TEXT_COLOR,
        link_color=link_color,
        link_text_color=link_text_color,
        link_type=html.escape(link.type.upper()),
        details=_detail_html(pc_node, "idaf-detail-pc") + _detail_html(router_node, "idaf-detail-router"),
    )
    components.html(body, height=380, scrolling=True)

    st.markdown("**Nodos y enlaces**")
    st.dataframe(
        [{"ID": n.id, "Etiqueta": n.label, "Tipo": n.type, "Estado": n.state.value} for n in graph.nodes]
        + [
            {
                "ID": f"{l.source} → {l.target}",
                "Etiqueta": l.type.upper(),
                "Tipo": "enlace",
                "Estado": l.state.value,
            }
            for l in graph.links
        ],
        use_container_width=True,
        hide_index=True,
    )
