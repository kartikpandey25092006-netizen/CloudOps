# Design System

This document outlines the existing UI design system found in the React dashboard.

## Typography
- Main font: System sans-serif (Inter/Roboto default via Tailwind/browser).
- Headers: Bold, clear contrast.
- Data values: Large text for metrics (e.g., Uptime, current CPU %).

## Colors
- **Theme:** Dark mode by default, with a toggle for light mode.
- **Backgrounds:** 
  - Dark: `#1a1b1e` (or similar dark gray/black).
  - Cards: Semi-transparent or slightly lighter gray for elevation.
- **Accents:**
  - Blue (`var(--accent-blue)`): Used for standard activity icons and successful self-healing actions.
  - Red (`var(--accent-red)`): Used for alarms, errors, and failed health checks.
  - Green (`var(--accent-green)`): Used for normal state or passed health checks.
- **Text:**
  - Primary text: High contrast (White in dark mode).
  - Secondary text (`var(--text-secondary)`): Muted gray for timestamps and minor details.

## Spacing & Layout
- A grid-based layout for metric cards at the top.
- A split layout below: Graphs on the left, Audit Logs on the right.
- Cards use padding and rounded corners.

## Components
- **Metric Cards:** Display icon, title, and large value.
- **Graphs:** Line charts using Recharts for CPU and Memory history.
- **Audit Log List:** A scrollable list of activity items with icons, timestamps, and colored statuses.
- **Maintenance Toggle:** A primary action button that visually indicates when the system is in maintenance mode.

## Loading, Error, Empty States
- **Loading:** Currently represented by a generic boolean `isLoading` state. Needs better skeleton loaders.
- **Error:** Some API errors are caught and logged to console, but lack explicit UI error states (e.g., "Failed to fetch metrics").
- **Empty States:** The audit log handles empty states by not rendering, but an explicit "No recent activity" message is preferred.

*Rule: Maintain this visual consistency when modifying the UI. Reuse existing CSS variables.*
