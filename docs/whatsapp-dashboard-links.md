# Referências de navegação do WhatsApp

Extensão compatível do `metadata` do envelope v1; não contém credenciais:

```json
{
  "candidate_id": 42,
  "dashboard_links": [{"href": "/app/candidaturas", "label": "Ver candidaturas"}],
  "dashboard_links_only": false,
  "dashboard_template_v2": false
}
```

`candidate_id` é o principal obtido pelo produtor confiável, nunca pela IA.
`href` é um caminho `/app` ou URL em origem oficial configurada. `label` é
informativo; a apresentação final usa o catálogo do transportador.
`dashboard_links_only` omite a bolha textual de pedidos exclusivos de navegação.
`dashboard_template_v2` identifica templates aprovados com um botão dinâmico em
`<DASHBOARD_ORIGIN>/auth/whatsapp#token={{1}}`; só o transportador preenche o token.

O whatsapp-worker valida a identidade com auth-api e resolve cada destino no
momento do envio. Reenvios usam a mesma emissão e recibos separados por parte.
Tokens não circulam no histórico do agente nem no outbox do produtor. URLs
internas embutidas em texto, legendas ou ações também passam pelo resolvedor.
