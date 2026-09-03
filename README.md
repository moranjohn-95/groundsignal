# groundsignal
Planning intelligence platform for discovering local construction opportunities from Irish planning data.

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Project Aims](#2-project-aims)
3. [Problem Statement](#3-problem-statement)
4. [Target Audience](#4-target-audience)
5. [User Goals](#5-user-goals)
6. [Product Value](#6-product-value)
7. [User Experience](#7-user-experience)
8. [User Stories & Agile Development](#8-user-stories--agile-development)
9. [Design](#9-design)
    - [Visual Design](#91-visual-design)
    - [Responsive Design](#92-responsive-design)
    - [Accessibility](#93-accessibility)
10. [Features](#10-features)
    - [Location Search](#101-location-search)
    - [Planning Opportunity Discovery](#102-planning-opportunity-discovery)
    - [Opportunity Scoring](#103-opportunity-scoring)
    - [Electrical Work Signals](#104-electrical-work-signals)
    - [Sorting & Pagination](#105-sorting--pagination)
    - [Opportunity Detail View](#106-opportunity-detail-view)
    - [Application States & Error Handling](#107-application-states--error-handling)
11. [Opportunity Scoring Logic](#11-opportunity-scoring-logic)
12. [Application Architecture](#12-application-architecture)
    - [Frontend](#121-frontend)
    - [Backend](#122-backend)
    - [API Layer](#123-api-layer)
    - [Database](#124-database)
13. [Planning Data & Data Pipeline](#13-planning-data--data-pipeline)
    - [Data Source](#131-data-source)
    - [Initial Import](#132-initial-import)
    - [Incremental Sync](#133-incremental-sync)
    - [Daily Reconciliation](#134-daily-reconciliation)
14. [API Endpoints](#14-api-endpoints)
15. [Database & Data Models](#15-database--data-models)
16. [Geocoding & Location Handling](#16-geocoding--location-handling)
17. [Security & Privacy](#17-security--privacy)
    - [API & Secret Management](#171-api--secret-management)
    - [Rate Limiting](#172-rate-limiting)
    - [Privacy-Safe Logging](#173-privacy-safe-logging)
    - [Security Headers](#174-security-headers)
18. [Data Licensing & Legal Considerations](#18-data-licensing--legal-considerations)
19. [Technologies Used](#19-technologies-used)
20. [Testing & Quality Assurance](#20-testing--quality-assurance)
    - [Backend Testing](#201-backend-testing)
    - [Frontend Testing](#202-frontend-testing)
    - [Linting & Build Validation](#203-linting--build-validation)
    - [Accessibility Testing](#204-accessibility-testing)
    - [Manual & Production Testing](#205-manual--production-testing)
21. [Continuous Integration](#21-continuous-integration)
22. [Docker & Local Development](#22-docker--local-development)
23. [Deployment](#23-deployment)
    - [AWS EC2](#231-aws-ec2)
    - [Docker Compose](#232-docker-compose)
    - [Nginx](#233-nginx)
    - [Frontend Deployment](#234-frontend-deployment)
    - [Automated Planning Sync](#235-automated-planning-sync)
24. [Environment Variables](#24-environment-variables)
25. [Local Installation & Setup](#25-local-installation--setup)
26. [Monitoring & Production Operations](#26-monitoring--production-operations)
27. [Bugs & Fixes](#27-bugs--fixes)
28. [Known Limitations](#28-known-limitations)
29. [Future Development](#29-future-development)
30. [Credits & Data Sources](#30-credits--data-sources)
31. [Acknowledgements](#31-acknowledgements)

## 2. Project Aims

The main aim of SiteForecaster is to help electrical contractors find relevant local construction opportunities without having to manually search through large volumes of planning application data.

Planning data is publicly available, but it can be difficult and time-consuming to work through. SiteForecaster takes this information and presents it in a more useful way by allowing users to search by location, review nearby planning applications, and quickly identify projects that may involve electrical work.

The project aims to:

- make Irish planning data easier to search and understand.
- help electrical contractors find potential work opportunities in their area.
- rank opportunities using a clear and consistent scoring system.
- highlight planning applications where electrical work is confirmed, likely, possible, or not specifically identified.
- provide enough information for users to decide which opportunities are worth investigating further.
- keep planning data reasonably up to date through automated background syncing.
- provide a responsive and accessible interface that works across desktop, tablet, and mobile devices.

From a development point of view, the project was also built to demonstrate how a modern full-stack application can be designed, tested, deployed, and maintained in a production environment.

## 3. Problem Statement

Irish planning application data contains useful information about upcoming construction and development projects. For tradespeople such as electricians, this can provide an early indication of where future work may become available.

The problem is that the raw planning data is not designed specifically for contractors looking for work. A large number of applications may need to be reviewed before finding one that is relevant, and important details can be spread across descriptions, development types, locations, and other fields.

For a small electrical contractor, manually searching this information regularly would take time and still make it easy to miss useful opportunities.

SiteForecaster addresses this by processing planning applications and presenting them through a contractor-focused interface. Applications can be searched by location and are given an opportunity score based on factors such as project scope, scale, timing, category, and signs of electrical work.

The aim is not to guarantee that a planning application will become a paid job. Instead, SiteForecaster helps reduce the amount of planning data a contractor needs to review and gives them a more focused starting point for finding potential opportunities.

## 4. Target Audience

The current version of SiteForecaster is aimed primarily at electrical contractors and electricians working in Ireland.

This includes:

- self-employed electricians looking for new local work.
- small electrical contracting businesses that want to identify upcoming projects.
- contractors who want to spend less time manually searching planning records.
- businesses interested in finding residential, commercial, industrial, public, or mixed-use developments that may require electrical work.

The platform is particularly useful for smaller contractors who may not have dedicated sales or business-development staff but still want an organised way to identify potential work in their area.

SiteForecaster is currently focused on electricians, but the underlying planning-data and opportunity-scoring approach could later be adapted for other construction trades if there is a clear business case.

## 5. User Goals

SiteForecaster is designed to help users find relevant planning opportunities quickly and with less manual searching.

The main user goals are to:

- search for planning opportunities near a chosen location.
- quickly understand which applications are most relevant.
- identify projects that may involve electrical work.
- compare opportunities using a clear scoring system.
- review useful project details without opening every planning record individually.
- sort and filter results so the strongest opportunities can be reviewed first.
- open the original planning application when more detail is needed.
- use the platform easily across desktop, tablet, and mobile devices.

The overall goal is to reduce the time spent searching through planning data and help users focus their attention on the applications most likely to be worth investigating.

## 6. Product Value

The value of SiteForecaster is not that it creates new planning data. The value comes from making existing public planning information easier to use for a specific type of contractor.

Instead of treating every planning application equally, SiteForecaster adds an extra layer of analysis. Applications are scored and ranked based on factors such as project scale, timing, category, scope, and signs of electrical work.

This helps users:

- spend less time reviewing low-value or irrelevant applications.
- spot stronger opportunities earlier.
- understand why one project may be more relevant than another.
- work from a more focused list of potential leads.
- use public planning information in a way that is more practical for business development.

SiteForecaster is intended to support decision-making rather than replace it. A high-scoring opportunity is not a guaranteed job, and users are still expected to review the original planning application before taking any further action.

## 7. User Experience

The user experience was designed around one main idea: finding useful planning opportunities should be quick and easy to understand.

A user can enter a location, choose a search radius, and view nearby planning applications without needing to understand the structure of the underlying planning dataset. Results are presented as opportunity cards with the most useful information shown first.

The interface gives particular attention to:

- clear opportunity scores and labels.
- simple electrical-work indicators.
- readable project descriptions and addresses.
- sorting options that help users prioritise stronger opportunities.
- clear loading, empty, error, and retry states.
- responsive layouts across desktop, tablet, and mobile devices.
- accessible headings, labels, focus states, and interactive controls.

The opportunity detail view provides more information when needed without overloading the main results page. Users can also follow the official planning application link if they want to verify the source information or investigate the project further.

The design avoids unnecessary complexity. The aim is to help a contractor understand the value of a planning application quickly, rather than forcing them to interpret technical planning data themselves.

## 8. User Stories & Agile Development

SiteForecaster was planned and tracked using a GitHub Agile board. The work was grouped into epics and user stories, which helped track progress from early development through to the current MVP stage.

### Agile Board Progression

GitHub Projects was used throughout development to track epics, user stories and their current status. The board used the workflow **Todo → In Progress → Testing / In Review → Done**, which made it easy to see what had been planned, what was actively being developed and what had been completed.

| Board Stage | Summary |
| --- | --- |
| During development | Board shows active work across Epics, Todo, In Progress and Done, reflecting the build-out of the MVP. |
| Current state | Board is now mostly complete, with the remaining open items focused on the README/documentation and future features such as authentication and shortlist saving. |

The earlier board below shows SiteForecaster during active MVP development. At this point, all seven main epics were still visible, several Must-have stories were waiting to be started, and core work such as planning classification, database migrations and automated testing was still in progress.

#### Agile Board During Development

![Agile board during development](docs/images/agile/agile-board-development.png)

As development progressed, completed stories and epics were moved into **Done**. Work was prioritised around the Must-have functionality needed for the MVP before moving on to lower-priority improvements.

The current board shows the result of that process. The main MVP engineering work is complete, with 28 items in **Done**. The remaining open stories are the README/documentation work currently being completed and two future features: user authentication and saved opportunity shortlists.

#### Current Agile Board

![Current Agile board](docs/images/agile/agile-board-current.png)

This progression provides a clear record of the project moving from planned epics and active development to a completed working MVP, while keeping future development separate from the functionality required for the initial release.

### Epic Summary

The work was grouped into epics to keep development organised and make the main areas of the MVP clear.

| Epic | Purpose | Status |
| --- | --- | --- |
| API Foundation & Application Architecture | Built the FastAPI backend structure and core application setup. | Complete |
| Location Search & Geocoding | Added location search, geocoding and current-location support. | Complete |
| Planning Data & Opportunity Discovery | Connected planning data and enabled discovery of nearby applications. | Complete |
| Opportunity Scoring & Prioritisation | Added opportunity scoring and ranking. | Complete |
| Database & Data Persistence | Added PostgreSQL/PostGIS persistence and database migrations. | Complete |
| Testing, CI/CD, Docker & AWS Deployment | Added containerisation, testing, CI and the deployment workflow. | Complete |
| User Experience & Tradesperson Dashboard | Delivered the dashboard, responsive UI, accessibility and production polish. | Complete |

### User Story Progress

User stories were prioritised using **Must-have**, **Should-have** and **Could-have** labels. Core MVP functionality was completed first, while lower-priority features were left for future development.

#### Must-have User Stories

All Must-have stories listed below have been completed.

| Must-have User Story | Outcome |
| --- | --- |
| Search & Geocode a Location | Users can search for an Irish location and receive usable coordinates. |
| Store & Query Planning Applications | Planning application data is stored and available through the API. |
| Find Nearby Planning Applications | Users can find planning applications near a selected location. |
| Classify Planning Applications by Opportunity Type | Applications are grouped by opportunity type to make results easier to review. |
| Score & Rank Commercial Opportunities | Opportunities are scored and ranked to help users focus on stronger leads. |
| Run GroundSignal with PostgreSQL & Database Migrations | The application uses PostgreSQL/PostGIS with managed schema migrations. |
| Automated Test Suite for Core Backend Features | Core backend behaviour is covered by automated tests. |
| Containerise GroundSignal with Docker | The backend and database can run in Docker containers. |
| Continuous Integration with GitHub Actions | Automated backend and frontend checks run through GitHub Actions. |
| Deploy GroundSignal to AWS | The application is deployed to AWS EC2. |
| Frontend Foundation & Application Structure | The React application has a structured component, routing and API setup. |
| Location Search Experience | Users can search by location or use their current location. |
| Opportunity Results Dashboard | Users can view ranked nearby opportunities in a clear results layout. |
| Opportunity Detail View & Score Explanation | Users can review project details and understand the opportunity score. |
| Responsive Design & Mobile Usability | The interface works across desktop, tablet and mobile devices. |
| Automated Planning Data Ingestion & Refresh | Planning data is imported and refreshed automatically. |
| Production Security & Configuration Hardening | Production configuration, dependency checks and privacy controls were reviewed and hardened. |

#### Should-have User Stories

The following Should-have stories were also completed as part of the MVP.

| Should-have User Story | Outcome |
| --- | --- |
| Filter & Sort Opportunities | Users can sort and filter results to focus on relevant opportunities. |
| UI Design System, Accessibility & User Feedback | The interface includes consistent styling, accessible controls and clear application states. |
| Frontend Testing & Core User Journey Validation | Important frontend journeys are covered by automated tests. |
| Production Health Monitoring & Operational Error Handling | A dedicated health check and production-safe operational monitoring approach were added. |

#### Remaining / Future User Stories

| User Story | Priority | Status | Reason |
| --- | --- | --- | --- |
| Project README, API Documentation & Architecture Guide | Must-have | In progress | Final project documentation is currently being completed. |
| User Accounts & Secure Authentication | Should-have | Future development | Authentication is useful but not required for the initial MVP. |
| Save & Manage Opportunity Shortlist | Could-have | Future development | Saving opportunities depends on user accounts and is outside the current MVP scope. |

#### Agile Workflow and Prioritisation

The board used a simple workflow: Todo, In Progress, Testing / In Review and Done. Work was prioritised so the core user value was delivered first. Must-have stories were completed before lower-priority future features, which kept the MVP focused and realistic.

### Development Outcome

The board shows clear progress from planning to delivery. The MVP is now largely complete, with documentation and future enhancements left open.

## Production Nginx and privacy-safe logging

Nginx is the production reverse proxy and static frontend server on EC2. Its
version-controlled configuration is in `deploy/nginx/`. The custom
`siteforecaster_safe` access-log format records the request method and `$uri`
path, but intentionally excludes query strings and referrers. This minimises
retention of user-entered location searches and coordinates. Uvicorn access
logging is disabled separately; Nginx error logging remains available.

### Install or update the Nginx configuration

From `/home/ubuntu/groundsignal` after deploying this repository revision:

```bash
sudo install -D -m 0644 deploy/nginx/siteforecaster-safe-logging.conf \
  /etc/nginx/conf.d/siteforecaster-safe-logging.conf
sudo install -D -m 0644 deploy/nginx/siteforecaster.conf \
  /etc/nginx/sites-available/siteforecaster
sudo ln -sfn /etc/nginx/sites-available/siteforecaster \
  /etc/nginx/sites-enabled/siteforecaster

sudo nginx -t
# Reload only after nginx -t succeeds.
sudo systemctl reload nginx
```

The live SSL certificate and private-key files referenced by this configuration
are managed separately. Never commit certificate or key material to this
repository.

## 26. Monitoring & Production Operations

`GET /health` returns `{"status": "ok"}` when the FastAPI process can serve
HTTP requests. It is a liveness check only: it does not query the database or
expose configuration, credentials, or infrastructure details. Docker Compose
uses this endpoint for the API container healthcheck, and Nginx proxies the
same exact path for external uptime checks.

On the EC2 host, check the application manually with:

```bash
curl -fsS https://siteforecaster.com/health
docker compose ps
docker compose logs --tail=100 api
sudo tail -n 100 /var/log/nginx/error.log
```

Docker health status, Nginx error logs, Docker API logs, and the existing
systemd planning-sync timer logs provide the MVP operational view. Privacy-safe
Nginx access logging and disabled Uvicorn access logging remain unchanged.

No external uptime alert is configured by this repository. As an optional
AWS-native manual step, create a CloudWatch alarm for the EC2 instance's
`StatusCheckFailed` metric: trigger when it is at least `1` for one five-minute
period, and send the notification to an SNS email topic with a confirmed
subscription. This monitors EC2 availability, not the application endpoint;
an external HTTP monitor can use `/health` if one is chosen later. Confirm AWS
account pricing and limits before enabling any alarm.

## Production planning-data sync

Planning applications are stored locally in PostgreSQL. The initial full import
is a separate operation; ongoing production freshness uses inclusive rolling
`ReceivedDate` windows. Existing applications are updated and missing ones are
inserted by source object ID, so repeating a window is safe and idempotent.

- The recent, near-real-time sync runs every 15 minutes with a 7-day window.
- A 90-day reconciliation runs daily at 03:15 UTC.
- `ETL_DATE` is deliberately not used as an incremental watermark because the
  source batch-refreshes older records.

Both jobs run inside the existing Docker Compose `api` container and are
scheduled by systemd timers on the Ubuntu EC2 host. The 7-day timer has been
verified in production with a successful `status=0` run.

### Install the systemd timers

From `/home/ubuntu/groundsignal` after deploying this repository revision:

```bash
sudo cp deploy/systemd/siteforecaster-planning-sync.service /etc/systemd/system/
sudo cp deploy/systemd/siteforecaster-planning-sync.timer /etc/systemd/system/
sudo cp deploy/systemd/siteforecaster-planning-reconcile.service /etc/systemd/system/
sudo cp deploy/systemd/siteforecaster-planning-reconcile.timer /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now siteforecaster-planning-sync.timer
sudo systemctl enable --now siteforecaster-planning-reconcile.timer
```

### Verify and operate

```bash
systemctl list-timers --all | grep siteforecaster
systemctl status siteforecaster-planning-sync.timer --no-pager
systemctl status siteforecaster-planning-reconcile.timer --no-pager
journalctl -u siteforecaster-planning-sync.service -n 50 --no-pager
journalctl -u siteforecaster-planning-reconcile.service -n 50 --no-pager
```

For a manual recent sync, the default window is 7 days:

```bash
docker compose exec -T api python -m backend.app.commands.planning_sync
docker compose exec -T api python -m backend.app.commands.planning_sync --days 90
```

### Classifier evaluation

The planning classifier assigns each application an opportunity type used by
the application. It is deterministic and rule-based, not a machine-learning
model.

Run the curated labelled regression benchmark with:

```bash
docker compose exec -T api python -m backend.app.commands.evaluate_planning_classifier --benchmark
```

The current benchmark contains 34 representative labelled cases across the
seven categories. It produced 34 correct classifications, 0 incorrect
classifications, and 100.0% accuracy. This is a regression benchmark, not an
independent random sample of production data. Planning descriptions can be
incomplete or ambiguous, so users should review the original application before
acting on an opportunity.

The default command samples database records for category distribution and
manual review, but cannot report accuracy because those source records do not
have human-assigned expected categories:

```bash
docker compose exec -T api python -m backend.app.commands.evaluate_planning_classifier --sample-size 500
```
