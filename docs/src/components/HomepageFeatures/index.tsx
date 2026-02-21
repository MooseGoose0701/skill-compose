import type {ReactNode} from 'react';
import styles from './styles.module.css';

type FeatureItem = {
  icon: string;
  title: string;
  description: ReactNode;
};

const FeatureList: FeatureItem[] = [
  {
    icon: '\u{1F9E9}',
    title: 'Skills as First-Class Artifacts',
    description: (
      <>
        Versioned, reviewable skill packages — contracts, references, rubrics,
        and helpers — not brittle workflow graphs.
      </>
    ),
  },
  {
    icon: '\u{1F4AC}',
    title: 'Conversational Agent Builder',
    description: (
      <>
        Describe what you want in plain language. Skill Compose finds, reuses,
        or drafts skills, then assembles a ready-to-run agent.
      </>
    ),
  },
  {
    icon: '\u{1F50C}',
    title: 'Tool & MCP Integration',
    description: (
      <>
        Built-in tools plus MCP servers give agents executable capabilities
        — code execution, web search, Git, and more — with zero glue code.
      </>
    ),
  },
  {
    icon: '\u{1F504}',
    title: 'Skill Evolution from Reality',
    description: (
      <>
        Improve skills automatically using execution traces and user feedback,
        with proposed rewrites you can review before merging.
      </>
    ),
  },
  {
    icon: '\u{1F680}',
    title: 'One-Click Publishing',
    description: (
      <>
        Ship agents as shareable Web Chat links or API endpoints in a single
        click — no extra infrastructure required.
      </>
    ),
  },
  {
    icon: '\u{1F433}',
    title: 'Container-First Execution',
    description: (
      <>
        Run code in isolated Docker containers with custom images — GPU stacks,
        ML libraries, or any environment your agents need.
      </>
    ),
  },
];

function Feature({icon, title, description}: FeatureItem) {
  return (
    <div className={styles.featureCard}>
      <div className={styles.featureIcon}>{icon}</div>
      <h3 className={styles.featureTitle}>{title}</h3>
      <p className={styles.featureDesc}>{description}</p>
    </div>
  );
}

export default function HomepageFeatures(): ReactNode {
  return (
    <section className={styles.features}>
      {FeatureList.map((props, idx) => (
        <Feature key={idx} {...props} />
      ))}
    </section>
  );
}
