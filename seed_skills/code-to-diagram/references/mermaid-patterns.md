# Mermaid Diagram Patterns

## Table of Contents
- [Architecture Diagram](#architecture-diagram)
- [ER Diagram](#er-diagram)
- [Sequence Diagram](#sequence-diagram)
- [Class Diagram](#class-diagram)
- [Flowchart](#flowchart)
- [State Diagram](#state-diagram)
- [Dependency Graph](#dependency-graph)
- [Gantt Chart](#gantt-chart)
- [Styling Tips](#styling-tips)

## Architecture Diagram

Use `graph TD` (top-down) or `graph LR` (left-right) with `subgraph` for layers.

```mermaid
graph TD
    Client["Browser / Mobile"]

    subgraph Frontend["Frontend :3000"]
        UI["React App"]
        Store["Redux Store"]
    end

    subgraph Backend["API Server :8000"]
        API["REST API"]
        Auth["Auth Middleware"]
        BL["Business Logic"]
    end

    subgraph Data["Data Layer"]
        DB[("PostgreSQL")]
        Cache[("Redis")]
        S3["S3 / Object Storage"]
    end

    Client --> UI
    UI --> Store
    UI --> API
    API --> Auth --> BL
    BL --> DB
    BL --> Cache
    BL --> S3
```

**Tips:**
- Use `[("...")]` for database cylinder shape
- Use `["..."]` for rectangles, `(["..."])` for rounded
- Group related components in `subgraph` with descriptive titles
- Add port numbers in subgraph titles for clarity

## ER Diagram

```mermaid
erDiagram
    users {
        uuid id PK
        varchar email UK
        varchar name
        timestamp created_at
    }

    orders {
        uuid id PK
        uuid user_id FK
        decimal total
        varchar status
        timestamp created_at
    }

    order_items {
        uuid id PK
        uuid order_id FK
        uuid product_id FK
        int quantity
        decimal price
    }

    products {
        uuid id PK
        varchar name
        decimal price
        int stock
    }

    users ||--o{ orders : places
    orders ||--|{ order_items : contains
    products ||--o{ order_items : "included in"
```

**Relationship symbols:**
- `||--||` one to one
- `||--o{` one to many
- `o{--o{` many to many
- `|` mandatory, `o` optional

**Tips:**
- Include PK/FK/UK annotations
- Use common SQL types: `uuid`, `varchar`, `int`, `decimal`, `timestamp`, `text`, `boolean`, `json`
- Quote relationship labels with spaces: `"included in"`

## Sequence Diagram

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant A as API
    participant DB as Database

    U->>F: Click "Submit"
    F->>A: POST /api/orders
    activate A
    A->>DB: INSERT INTO orders
    DB-->>A: order_id
    A->>A: Validate & process
    A-->>F: 201 Created {id}
    deactivate A
    F-->>U: Show confirmation

    alt Payment fails
        A-->>F: 400 Bad Request
        F-->>U: Show error
    end
```

**Arrow types:**
- `->>` solid line with arrowhead (sync call)
- `-->>` dashed line with arrowhead (response)
- `--)` async message

**Tips:**
- Use `participant X as "Short Name"` for readability
- `activate`/`deactivate` to show lifeline
- `alt`/`else` for conditional branches
- `loop` for repeated operations
- `Note over A,B: text` for annotations

## Class Diagram

```mermaid
classDiagram
    class Animal {
        +String name
        +int age
        +makeSound() String
    }

    class Dog {
        +String breed
        +fetch() void
        +makeSound() String
    }

    class Cat {
        +bool indoor
        +purr() void
        +makeSound() String
    }

    class Shelter {
        -List~Animal~ animals
        +addAnimal(Animal a) void
        +getCount() int
    }

    Animal <|-- Dog : extends
    Animal <|-- Cat : extends
    Shelter o-- Animal : houses
```

**Visibility:**
- `+` public, `-` private, `#` protected, `~` package

**Relationships:**
- `<|--` inheritance
- `*--` composition
- `o--` aggregation
- `-->` association
- `..>` dependency

## Flowchart

```mermaid
flowchart TD
    Start([Start]) --> Input[/Read user input/]
    Input --> Validate{Valid?}
    Validate -->|Yes| Process[Process data]
    Validate -->|No| Error[Show error]
    Error --> Input
    Process --> Save[(Save to DB)]
    Save --> Notify[/Send notification/]
    Notify --> End([End])
```

**Node shapes:**
- `[text]` rectangle
- `(text)` rounded
- `{text}` diamond (decision)
- `[(text)]` cylinder (database)
- `([text])` stadium (start/end)
- `[/text/]` parallelogram (I/O)

## State Diagram

```mermaid
stateDiagram-v2
    [*] --> Draft
    Draft --> Pending : submit
    Pending --> Approved : approve
    Pending --> Rejected : reject
    Rejected --> Draft : revise
    Approved --> Published : publish
    Published --> Archived : archive
    Archived --> [*]

    state Pending {
        [*] --> UnderReview
        UnderReview --> NeedsChanges : request changes
        NeedsChanges --> UnderReview : resubmit
        UnderReview --> Ready : approve
    }
```

## Dependency Graph

Use `graph LR` for module dependency visualization:

```mermaid
graph LR
    main --> api
    main --> config
    api --> auth
    api --> handlers
    handlers --> services
    services --> db
    services --> cache
    auth --> db
    config --> db
```

## Gantt Chart

```mermaid
gantt
    title Project Timeline
    dateFormat YYYY-MM-DD

    section Design
    Requirements     :done, req, 2024-01-01, 2024-01-14
    UI Design        :done, ui, after req, 14d

    section Development
    Backend API      :active, api, after ui, 21d
    Frontend         :fe, after ui, 28d

    section Testing
    Integration Test :test, after api, 14d
    UAT              :uat, after fe, 7d
```

## Styling Tips

### Theme
mmdc supports themes via config:
```json
{
  "theme": "default"
}
```
Available: `default`, `dark`, `forest`, `neutral`. Pass via `-c config.json` to mmdc.

### Large Diagrams
When a diagram exceeds ~20 nodes:
1. Split into multiple diagrams by domain/layer
2. Create an overview diagram linking to detail diagrams
3. Use `graph LR` (horizontal) for wide dependency trees
4. Use `graph TD` (vertical) for deep hierarchies

### Text in Labels
- Quote strings with special characters: `A["API (v2)"]`
- Use `<br/>` for line breaks in labels: `A["Line 1<br/>Line 2"]`
- Avoid `--` in labels (conflicts with Mermaid syntax)
