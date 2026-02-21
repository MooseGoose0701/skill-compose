import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'Skill Compose',
  tagline: 'Describe. Compose. Evolve.',
  favicon: 'img/logo.png',

  future: {
    v4: true,
  },

  headTags: [
    {
      tagName: 'link',
      attributes: {rel: 'preconnect', href: 'https://fonts.googleapis.com'},
    },
    {
      tagName: 'link',
      attributes: {rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: 'anonymous'},
    },
    {
      tagName: 'link',
      attributes: {
        rel: 'stylesheet',
        href: 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap',
      },
    },
  ],

  url: 'https://skill-compose.dev',
  baseUrl: '/',

  organizationName: 'MooseGoose0701',
  projectName: 'skill-compose',

  onBrokenLinks: 'throw',

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  markdown: {
    mermaid: true,
  },

  themes: ['@docusaurus/theme-mermaid'],

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/MooseGoose0701/skill-compose/tree/main/docs/',
          routeBasePath: '/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: 'img/social-card.png',
    announcementBar: {
      id: 'github_star',
      content: 'If you like Skill Compose, give it a \u2B50 on <a href="https://github.com/MooseGoose0701/skill-compose" target="_blank" rel="noopener noreferrer">GitHub</a>!',
      isCloseable: true,
    },
    colorMode: {
      defaultMode: 'light',
      respectPrefersColorScheme: false,
    },
    navbar: {
      title: 'Skill Compose',
      logo: {
        alt: 'Skill Compose Logo',
        src: 'img/logo.png',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: 'Docs',
        },
        {
          href: 'https://github.com/MooseGoose0701/skill-compose',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Get Started',
          items: [
            {
              label: 'Installation',
              to: '/quickstart',
            },
            {
              label: 'Quickstart',
              to: '/quickstart',
            },
          ],
        },
        {
          title: 'Learn',
          items: [
            {
              label: 'Concepts',
              to: '/concepts/agents',
            },
            {
              label: 'How-To Guides',
              to: '/how-to/create-agent',
            },
            {
              label: 'API Reference',
              to: '/reference/api',
            },
          ],
        },
        {
          title: 'More',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/MooseGoose0701/skill-compose',
            },
          ],
        },
      ],
      copyright: `Copyright \u00A9 ${new Date().getFullYear()} Skill Compose`,
    },
    mermaid: {
      theme: {
        light: 'neutral',
        dark: 'dark',
      },
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['bash', 'yaml', 'json', 'python', 'docker', 'toml'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
