# Project proposal

## Purpose

SIBERLENS AI is a defensive social cyber intelligence early-warning prototype intended to help analysts review authorized, documented data sources and respond responsibly.

## Current foundation

The current release establishes the React/Vite dashboard shell, a versioned FastAPI health endpoint, PostgreSQL configuration, and the initial datasets/posts/analyses/alerts schema. The dashboard reports empty states; it does not imply live collection or analysis.

## Scope boundaries

The foundation does not collect social data, authenticate users, call an LLM, perform clustering or anomaly detection, or generate alerts or reports. Future capabilities require defined authorization, provenance, data minimization, retention, validation, and human review.
