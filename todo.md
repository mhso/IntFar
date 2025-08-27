# LAN
Lav et script der automatisk laver scaffolding. Følgende ting kan scaffoldes:

## LAN stuff
- Indsæt ny entry i `LAN_PARTIES ` i `api/lan.py`

## Jeopardy stuff
- Bump `JEOPARDY_ITERATION` i `api/util.py`
- Opret mappe med ny version i `app/static/img/jeopardy`
- Opret nye tomme filer for `jeopardy_questions_{JEOPARDY_ITERATION}.json` og `jeopardy_used_{JEOPARDY_ITERATION}.json` i `app/static/data`