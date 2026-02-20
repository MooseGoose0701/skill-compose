<p align="center">
  <img src="scheader.png" alt="Skill Compose" width="50%" />
</p>

<p align="center">
  <a href="./README.md"><img alt="English" src="https://img.shields.io/badge/English-d9d9d9"></a>
  <a href="./README_es.md"><img alt="Español" src="https://img.shields.io/badge/Español-d9d9d9"></a>
  <a href="./README_pt-BR.md"><img alt="Português (BR)" src="https://img.shields.io/badge/Português (BR)-d9d9d9"></a>
  <a href="./README_zh-CN.md"><img alt="简体中文" src="https://img.shields.io/badge/简体中文-d9d9d9"></a>
  <a href="./README_ja.md"><img alt="日本語" src="https://img.shields.io/badge/日本語-d9d9d9"></a>
</p>

<p align="center">
Skill Compose es una plataforma de código abierto para construir y ejecutar agentes impulsados por habilidades.<br>
Sin grafos de flujo. Sin CLI.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License" /></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11+-green.svg" alt="Python" /></a>
  <a href="https://nextjs.org/"><img src="https://img.shields.io/badge/Next.js-14-black.svg" alt="Next.js" /></a>
  <a href="https://discord.gg/uRDx9hJj"><img src="https://img.shields.io/badge/Discord-%235865F2.svg?style=flat&logo=discord&logoColor=white" alt="discord" /></a>
  <a href="https://x.com/SkillComposeAI/"><img src="https://img.shields.io/twitter/follow/SkillComposeAI" alt="twitter" /></a>
</p>

<p align="center">
  <img src="docs/images/screenshot.png" alt="Captura de pantalla de Skill Compose" width="800" />
</p>

## Capacidades Clave

- 🧩 **Habilidades como artefactos de primera clase** — paquetes de habilidades versionados y revisables (contratos, referencias, rúbricas, helpers), no grafos frágiles.
- 🧠 **Flujo de trabajo "Skill-Compose My Agent"** — describe lo que necesitas; Skill Compose encuentra/reutiliza habilidades, redacta las faltantes y compone un agente.
- 🔌 **Conexión de herramientas + MCP** — conecta herramientas y servidores MCP sin escribir código de integración manualmente.
- 🚀 **Publicación instantánea** — un clic para desplegar como **Chat Web** (enlace compartible) y/o **API** (endpoint listo para integraciones).
- 🛡️ **Aislamiento con contenedores** — ejecuta agentes en contenedores (o pods de K8s) para mantener el host limpio y la ejecución reproducible.
- 🧱 **Executors para entornos pesados** — asigna imágenes Docker personalizadas / runtimes de K8s por agente (stacks GPU/ML/HPC, builds personalizados).
- 📦 **Gestión del ciclo de vida de habilidades** — importación desde GitHub + actualizaciones con un clic, importación/exportación multiformato, historial de versiones, diff/rollback y sincronización local.
- 🔄 **Evolución de habilidades basada en la realidad** — mejora habilidades usando feedback y trazas de ejecución, con reescrituras propuestas que puedes revisar.
- 🗂️ **Organización de la biblioteca de habilidades** — categorías, fijado y descubrimiento ligero para mantener el orden con más de 100 habilidades.

## Ejemplos

<table>
<tr>
<td align="center">
<b>Skill-Compose Tu Agente</b><br>
<sub>Describe lo que necesitas y deja que Skill Compose construya el agente por ti — encontrando habilidades existentes, redactando las faltantes y conectando todo.</sub><br><br>
<img src="docs/examples/skill-compose-your-agent.gif" alt="Skill-Compose Tu Agente" width="100%" />
</td>
</tr>
<tr>
<td align="center">
<b>Evoluciona Tu Agente</b><br>
<sub>Mejora habilidades automáticamente a partir de trazas de ejecución y feedback de usuarios, revisa los cambios propuestos, acepta la reescritura y observa cómo tus agentes y habilidades se vuelven más inteligentes.</sub><br><br>
<img src="docs/examples/evolve-your-agent.gif" alt="Evoluciona Tu Agente" width="100%" />
</td>
</tr>
<tr>
<td align="center">
<b>Agente Demo: Artículo a Diapositivas</b><br>
<sub>Convierte cualquier artículo o paper en una presentación pulida. El agente lee el contenido, extrae puntos clave, redacta storyboards y genera diapositivas listas para presentar.</sub><br><br>
<img src="docs/examples/article-to-slides-agent.gif" alt="Agente Artículo a Diapositivas" width="100%" />
</td>
</tr>
<tr>
<td align="center">
<b>Agente Demo: ChemScout</b><br>
<sub>¡Se ejecuta en un entorno aislado! Un asistente de investigación química que busca en bases de datos de compuestos, analiza estructuras moleculares y resume hallazgos en informes estructurados.</sub><br><br>
<img src="docs/examples/chemscout-agent.gif" alt="Agente ChemScout" width="100%" />
</td>
</tr>
</table>

## Arquitectura

<p align="center">
  <img src="docs/images/architecture.png" alt="Arquitectura de Skill Compose" width="700" />
</p>

*Algunas funcionalidades mostradas pueden estar aún en desarrollo.*

## Inicio Rápido

Comienza con Docker:

```bash
git clone https://github.com/MooseGoose0701/skill-compose.git
cd skill-compose/docker
# El modelo por defecto es Kimi 2.5 (API key: MOONSHOT_API_KEY), agrega al menos una API key de LLM.
# También puedes configurar las API keys manualmente en la página "Environment" de la Web UI después del lanzamiento.
cp .env.example .env
docker compose up -d
```

Abre **http://localhost:62600** y haz clic en **"Skill-Compose Your Agent"**.

Detener servicios:

```bash
cd skill-compose/docker
docker compose down
```

<details>
<summary>Compilar desde el código fuente (para desarrolladores)</summary>

```bash
cd skill-compose/docker
cp .env.example .env
# Usar docker-compose.dev.yaml para compilar imágenes localmente
docker compose -f docker-compose.dev.yaml up -d
# Después de cambios en el código, redesplegar (detener, compilar, reiniciar):
./redeploy.sh          # todos los servicios
./redeploy.sh api      # solo API
./redeploy.sh web      # solo Web
```

</details>

<details>
<summary>Limpieza (restablecer al estado inicial)</summary>

```bash
cd skill-compose/docker
# '-v' eliminará todos los datos almacenados en los volúmenes
docker compose down -v
```

</details>

## Recursos

- 📚 [Documentación completa](docs/) — Primeros pasos, conceptos, guías prácticas y referencia
- 🔧 [Referencia de API](docs/docs/reference/api.md) — Endpoints completos de la API REST
- 🤖 [Modelos y proveedores](docs/docs/concepts/models.md) — LLMs soportados y configuración

## Contribuciones

¿Encontraste un bug o tienes una idea de funcionalidad? ¡Las contribuciones son bienvenidas!

## Licencia

Apache License 2.0 — consulta [LICENSE](LICENSE) para más detalles.
