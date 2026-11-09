# Draft issue for mozilla-ai/otari (file under the tobadaniel account)

Title: Hosted dashboard: key creation rejects picker-offered model id
mistralai/mistral-small-3 as "unknown provider or instance 'mistralai'"

Body:
On otari.ai (hosted), creating a workspace API key with model scoping
"Only selected" and choosing mistralai/mistral-small-3 from the
dashboard's own model picker fails at submit with:

'mistralai/mistral-small-3': unknown provider or instance 'mistralai'

Steps: Dashboard -> API keys -> Create key -> Advanced -> Only
selected -> search "mistral" -> select mistralai/mistral-small-3
(picker labels it "(mistralai)") -> Create key.

Expected: the key is created scoped to the selected model, since the
Models tab lists it and the picker offers it.
Actual: server rejects the provider/instance as unknown. Selecting
openai/gpt-oss-20b in the same flow was accepted (the failure named
only mistralai). Workaround: scope "Inherit your access".

Environment: hosted otari.ai, fresh workspace created 2026-11-09,
browser dashboard. Found during the Devs Wilding hackathon.
