### Event Management

Event Management Platform

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench install-app event_management
```
###Videos

[Screencast from 2026-11-06 01-47-43.webm](https://github.com/user-attachments/assets/d8e0dca9-d2a1-4731-bb66-8c0b4e2d8312)

[Screencast from 2026-11-06 01-47-43.webm](https://github.com/user-attachments/assets/7876b3b3-5d7d-4112-87ef-1cf6f1f680df)

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/event_management
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit
