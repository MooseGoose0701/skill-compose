// Static imports of all translation JSON files (15 namespaces × 5 languages)
// Bundled at build time for synchronous i18next initialization (no flash)

// en-US
import enCommon from './locales/en-US/common.json'
import enHome from './locales/en-US/home.json'
import enSkills from './locales/en-US/skills.json'
import enAgents from './locales/en-US/agents.json'
import enChat from './locales/en-US/chat.json'
import enTools from './locales/en-US/tools.json'
import enMcp from './locales/en-US/mcp.json'
import enTraces from './locales/en-US/traces.json'
import enFiles from './locales/en-US/files.json'
import enSettings from './locales/en-US/settings.json'
import enBackup from './locales/en-US/backup.json'
import enExecutors from './locales/en-US/executors.json'
import enImport from './locales/en-US/import.json'
import enSessions from './locales/en-US/sessions.json'
import enTerminal from './locales/en-US/terminal.json'

// zh-CN
import zhCommon from './locales/zh-CN/common.json'
import zhHome from './locales/zh-CN/home.json'
import zhSkills from './locales/zh-CN/skills.json'
import zhAgents from './locales/zh-CN/agents.json'
import zhChat from './locales/zh-CN/chat.json'
import zhTools from './locales/zh-CN/tools.json'
import zhMcp from './locales/zh-CN/mcp.json'
import zhTraces from './locales/zh-CN/traces.json'
import zhFiles from './locales/zh-CN/files.json'
import zhSettings from './locales/zh-CN/settings.json'
import zhBackup from './locales/zh-CN/backup.json'
import zhExecutors from './locales/zh-CN/executors.json'
import zhImport from './locales/zh-CN/import.json'
import zhSessions from './locales/zh-CN/sessions.json'
import zhTerminal from './locales/zh-CN/terminal.json'

// ja
import jaCommon from './locales/ja/common.json'
import jaHome from './locales/ja/home.json'
import jaSkills from './locales/ja/skills.json'
import jaAgents from './locales/ja/agents.json'
import jaChat from './locales/ja/chat.json'
import jaTools from './locales/ja/tools.json'
import jaMcp from './locales/ja/mcp.json'
import jaTraces from './locales/ja/traces.json'
import jaFiles from './locales/ja/files.json'
import jaSettings from './locales/ja/settings.json'
import jaBackup from './locales/ja/backup.json'
import jaExecutors from './locales/ja/executors.json'
import jaImport from './locales/ja/import.json'
import jaSessions from './locales/ja/sessions.json'
import jaTerminal from './locales/ja/terminal.json'

// es
import esCommon from './locales/es/common.json'
import esHome from './locales/es/home.json'
import esSkills from './locales/es/skills.json'
import esAgents from './locales/es/agents.json'
import esChat from './locales/es/chat.json'
import esTools from './locales/es/tools.json'
import esMcp from './locales/es/mcp.json'
import esTraces from './locales/es/traces.json'
import esFiles from './locales/es/files.json'
import esSettings from './locales/es/settings.json'
import esBackup from './locales/es/backup.json'
import esExecutors from './locales/es/executors.json'
import esImport from './locales/es/import.json'
import esSessions from './locales/es/sessions.json'
import esTerminal from './locales/es/terminal.json'

// pt-BR
import ptCommon from './locales/pt-BR/common.json'
import ptHome from './locales/pt-BR/home.json'
import ptSkills from './locales/pt-BR/skills.json'
import ptAgents from './locales/pt-BR/agents.json'
import ptChat from './locales/pt-BR/chat.json'
import ptTools from './locales/pt-BR/tools.json'
import ptMcp from './locales/pt-BR/mcp.json'
import ptTraces from './locales/pt-BR/traces.json'
import ptFiles from './locales/pt-BR/files.json'
import ptSettings from './locales/pt-BR/settings.json'
import ptBackup from './locales/pt-BR/backup.json'
import ptExecutors from './locales/pt-BR/executors.json'
import ptImport from './locales/pt-BR/import.json'
import ptSessions from './locales/pt-BR/sessions.json'
import ptTerminal from './locales/pt-BR/terminal.json'

export const resources = {
  'en-US': {
    common: enCommon,
    home: enHome,
    skills: enSkills,
    agents: enAgents,
    chat: enChat,
    tools: enTools,
    mcp: enMcp,
    traces: enTraces,
    files: enFiles,
    settings: enSettings,
    backup: enBackup,
    executors: enExecutors,
    import: enImport,
    sessions: enSessions,
    terminal: enTerminal,
  },
  'zh-CN': {
    common: zhCommon,
    home: zhHome,
    skills: zhSkills,
    agents: zhAgents,
    chat: zhChat,
    tools: zhTools,
    mcp: zhMcp,
    traces: zhTraces,
    files: zhFiles,
    settings: zhSettings,
    backup: zhBackup,
    executors: zhExecutors,
    import: zhImport,
    sessions: zhSessions,
    terminal: zhTerminal,
  },
  ja: {
    common: jaCommon,
    home: jaHome,
    skills: jaSkills,
    agents: jaAgents,
    chat: jaChat,
    tools: jaTools,
    mcp: jaMcp,
    traces: jaTraces,
    files: jaFiles,
    settings: jaSettings,
    backup: jaBackup,
    executors: jaExecutors,
    import: jaImport,
    sessions: jaSessions,
    terminal: jaTerminal,
  },
  es: {
    common: esCommon,
    home: esHome,
    skills: esSkills,
    agents: esAgents,
    chat: esChat,
    tools: esTools,
    mcp: esMcp,
    traces: esTraces,
    files: esFiles,
    settings: esSettings,
    backup: esBackup,
    executors: esExecutors,
    import: esImport,
    sessions: esSessions,
    terminal: esTerminal,
  },
  'pt-BR': {
    common: ptCommon,
    home: ptHome,
    skills: ptSkills,
    agents: ptAgents,
    chat: ptChat,
    tools: ptTools,
    mcp: ptMcp,
    traces: ptTraces,
    files: ptFiles,
    settings: ptSettings,
    backup: ptBackup,
    executors: ptExecutors,
    import: ptImport,
    sessions: ptSessions,
    terminal: ptTerminal,
  },
} as const
