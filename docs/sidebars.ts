import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    'introduction',
    'quickstart',
    'development-setup',
    {
      type: 'category',
      label: 'Concepts',
      items: [
        'concepts/agents',
        'concepts/memory',
        'concepts/skills',
        'concepts/executors',
        'concepts/tools',
        'concepts/mcp',
        'concepts/models',
      ],
    },
    {
      type: 'category',
      label: 'How-To Guides',
      items: [
        'how-to/create-agent',
        'how-to/create-skill',
        'how-to/evolve-skills',
        'how-to/import-export-skills',
        'how-to/use-external-skills',
        'how-to/publish-agent',
        'how-to/configure-mcp',
        'how-to/build-custom-executor',
        'how-to/backup-restore',
        'how-to/run-tests',
      ],
    },
    {
      type: 'category',
      label: 'Reference',
      items: [
        'reference/api',
        'reference/skill-format',
        'reference/configuration',
      ],
    },
    'faq',
  ],
};

export default sidebars;
