# Architecture

```text
CLI / Future FastAPI / Workers
            |
            v
     Connection Layer
            |
            v
      Manifest Factory
            |
            v
 UniversalCommerceConnector
            |
   +--------+--------+
   |        |        |
Protocol   Auth   Pagination
   |        |        |
   +--------+--------+
            |
        Transport
            |
      External API
            |
       Raw Response
            |
      Response Parser
            |
      ConnectorPage
```

Platform-specific API knowledge belongs in YAML. Core execution code remains capability-driven.
