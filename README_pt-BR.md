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
Skill Compose é uma plataforma open-source para construir e executar agentes baseados em habilidades.<br>
Sem grafos de fluxo. Sem CLI.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License" /></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11+-green.svg" alt="Python" /></a>
  <a href="https://nextjs.org/"><img src="https://img.shields.io/badge/Next.js-14-black.svg" alt="Next.js" /></a>
  <a href="https://discord.gg/uRDx9hJj"><img src="https://img.shields.io/badge/Discord-%235865F2.svg?style=flat&logo=discord&logoColor=white" alt="discord" /></a>
  <a href="https://x.com/SkillComposeAI/"><img src="https://img.shields.io/twitter/follow/SkillComposeAI" alt="twitter" /></a>
</p>

<p align="center">
  <img src="docs/images/screenshot.png" alt="Captura de tela do Skill Compose" width="800" />
</p>

## Capacidades Principais

- 🧩 **Habilidades como artefatos de primeira classe** — pacotes de habilidades versionados e revisáveis (contratos, referências, rubricas, helpers), não grafos frágeis.
- 🧠 **Fluxo de trabalho "Skill-Compose My Agent"** — descreva o que você precisa; o Skill Compose encontra/reutiliza habilidades, redige as que faltam e compõe um agente.
- 🔌 **Conexão de ferramentas + MCP** — conecte ferramentas e servidores MCP sem escrever código de integração manualmente.
- 🚀 **Publicação instantânea** — um clique para implantar como **Chat Web** (link compartilhável) e/ou **API** (endpoint pronto para integrações).
- 🛡️ **Isolamento com containers** — execute agentes em containers (ou pods K8s) para manter o host limpo e a execução reproduzível.
- 🧱 **Executors para ambientes pesados** — atribua imagens Docker personalizadas / runtimes K8s por agente (stacks GPU/ML/HPC, builds personalizados).
- 📦 **Gestão do ciclo de vida de habilidades** — importação do GitHub + atualizações com um clique, importação/exportação multiformato, histórico de versões, diff/rollback e sincronização local.
- 🔄 **Evolução de habilidades baseada na realidade** — melhore habilidades usando feedback e traces de execução, com reescritas propostas que você pode revisar.
- 🗂️ **Organização da biblioteca de habilidades** — categorias, fixação e descoberta leve para manter a organização com mais de 100 habilidades.

## Exemplos

<table>
<tr>
<td align="center">
<b>Skill-Compose Seu Agente</b><br>
<sub>Descreva o que você precisa e deixe o Skill Compose construir o agente para você — encontrando habilidades existentes, redigindo as que faltam e conectando tudo.</sub><br><br>
<img src="docs/examples/skill-compose-your-agent.gif" alt="Skill-Compose Seu Agente" width="100%" />
</td>
</tr>
<tr>
<td align="center">
<b>Evolua Seu Agente</b><br>
<sub>Melhore habilidades automaticamente a partir de traces de execução e feedback de usuários, revise as mudanças propostas, aceite a reescrita e veja seus agentes e habilidades ficarem mais inteligentes.</sub><br><br>
<img src="docs/examples/evolve-your-agent.gif" alt="Evolua Seu Agente" width="100%" />
</td>
</tr>
<tr>
<td align="center">
<b>Agente Demo: Artigo para Slides</b><br>
<sub>Transforme qualquer artigo ou paper em uma apresentação polida. O agente lê o conteúdo, extrai pontos-chave, elabora storyboards e gera slides prontos para apresentação.</sub><br><br>
<img src="docs/examples/article-to-slides-agent.gif" alt="Agente Artigo para Slides" width="100%" />
</td>
</tr>
<tr>
<td align="center">
<b>Agente Demo: ChemScout</b><br>
<sub>Executa em um ambiente isolado! Um assistente de pesquisa química que busca em bancos de dados de compostos, analisa estruturas moleculares e resume descobertas em relatórios estruturados.</sub><br><br>
<img src="docs/examples/chemscout-agent.gif" alt="Agente ChemScout" width="100%" />
</td>
</tr>
</table>

## Arquitetura

<p align="center">
  <img src="docs/images/architecture.png" alt="Arquitetura do Skill Compose" width="700" />
</p>

*Algumas funcionalidades mostradas podem ainda estar em desenvolvimento.*

## Início Rápido

Comece com Docker:

```bash
git clone https://github.com/MooseGoose0701/skill-compose.git
cd skill-compose/docker
# O modelo padrão é Kimi 2.5 (API key: MOONSHOT_API_KEY), adicione pelo menos uma API key de LLM.
# Você também pode configurar as API keys manualmente na página "Environment" da Web UI após o lançamento.
cp .env.example .env
docker compose up -d
```

Abra **http://localhost:62600** e clique em **"Skill-Compose Your Agent"**.

Parar serviços:

```bash
cd skill-compose/docker
docker compose down
```

<details>
<summary>Compilar a partir do código-fonte (para desenvolvedores)</summary>

```bash
cd skill-compose/docker
cp .env.example .env
# Usar docker-compose.dev.yaml para compilar imagens localmente
docker compose -f docker-compose.dev.yaml up -d
# Após alterações no código, reimplantar (parar, compilar, reiniciar):
./redeploy.sh          # todos os serviços
./redeploy.sh api      # apenas API
./redeploy.sh web      # apenas Web
```

</details>

<details>
<summary>Limpeza (redefinir para o estado inicial)</summary>

```bash
cd skill-compose/docker
# '-v' removerá todos os dados armazenados nos volumes
docker compose down -v
```

</details>

## Recursos

- 📚 [Documentação completa](docs/) — Primeiros passos, conceitos, guias práticos e referência
- 🔧 [Referência da API](docs/docs/reference/api.md) — Endpoints completos da API REST
- 🤖 [Modelos e provedores](docs/docs/concepts/models.md) — LLMs suportados e configuração

## Contribuições

Encontrou um bug ou tem uma ideia de funcionalidade? Contribuições são bem-vindas!

## Licença

Apache License 2.0 — veja [LICENSE](LICENSE) para detalhes.
