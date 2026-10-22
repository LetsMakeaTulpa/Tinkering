# Night Map and Day Map — Project Plan

## Safety rule

This plan is being developed on the `night-day-map-foundation` branch. Keep the existing `main` branch and its Flask Hello World app unchanged until the new work has been reviewed and tested.

## Product direction

### Night Map

A dark, mobile-friendly, practical San Francisco atlas designed for outsiders and night-time city navigation. Potential categories include water, bathrooms, food, charging, Wi-Fi, shelters, showers, libraries, public services, and community discoveries.

Privacy is a core requirement: location sharing is off by default; do not publish vulnerable people's precise locations; do not claim live data is available unless a real source is connected.

### Day Map

A separate, polished historical San Francisco atlas for residents, visitors, artists, and researchers. Focus on historical maps, archival photographs, past street names, changing shorelines, buildings, timelines, oral histories, and citations.

Historical claims must be source-linked. Clearly label AI-generated reconstructions and unverified leads; never present them as archival evidence.

## Shared data principles

- Give each place a stable identifier and coordinates when known.
- Preserve alternate names and historical names.
- Store historical events separately rather than assuming one date per place.
- Track sources, verification dates, uncertainty, and access notes.
- Keep original source material distinct from AI-generated interpretation.
- Mark sample/demo records clearly.
- Support export and backup before introducing complex features.

## Suggested first milestone

1. Review the existing Flask application and preserve it.
2. Create a minimal working prototype on this branch.
3. Keep Night Map and Day Map as distinct user experiences.
4. Add a small shared place-data format.
5. Make local demo data and forms clearly distinguishable from verified live information.
6. Document how to run and test the project.
7. Review the diff and test before merging anything into `main`.

## Existing application

The repository currently has a minimal Flask app in `app.py`, with dependencies listed in `requirements.txt`. Do not remove or replace this app until a tested migration plan has been agreed upon.
