### Updated Parts Manager System Plan: Active Jobs, Trucks, User Assignments, and LLM Background Tasks

This update integrates the new requirements into the electrician-focused Parts Manager app. Key additions:
- **Truck Assignments**: Each user (electrician) is assigned to a specific truck (their "signed vehicle"), with a shared truck list showing assignments.
- **Active Jobs**: Users have prioritized "active jobs" they're working on (not strictly locked, but focused). Access is restricted to active jobs only—users can't view/edit inactive ones.
- **Job Consumption Tracking**: Quick, easy logging of parts consumed on jobs (e.g., one-click deductions from truck stock during job execution).
- **LLM Background Tasks**: Use the local desktop LLM for administrative agents that handle hard-to-code tasks in the background. These small agents will use a couple of custom "MCP tools" (interpreting as "Minimal Custom Protocol tools" or simple API-like hooks; e.g., DB query tools, notification tools) to automate lookups, add items (e.g., "add cards" as adding parts/inventory cards), ask clarifying questions (via app prompts), remind of audits, and periodically scan for inconsistencies (e.g., mismatched stock levels, lost parts) to ensure accuracy.

The app remains **desktop-only, offline-first, multi-user** with **heavy local processing**. LLM runs in background threads for non-blocking tasks (e.g., periodic audits every hour or on app idle). Agents are "small" and focused: Built on the repo's orchestration (Planning/Answer/Verification) with custom tools like DB access or user notification hooks.

Below, features and goals are listed for the new/relevant components: User/Truck Assignments, Active Jobs Management, Parts Consumption on Jobs, and LLM Background Agents.

#### User and Truck Assignments
| Perspective | Features | Goals |
|-------------|----------|-------|
| User | - Truck list view: See all trucks with assigned users (e.g., "Truck #3: Assigned to User A").<br>- Personal assignment: Each user sees their "signed vehicle" highlighted.<br>- Multi-user sharing: Admins can reassign trucks; users see team assignments.<br>- Filter trucks by active jobs or availability. | - Clear visibility of who has which truck for coordination.<br>- Prioritize user's own truck for quick access to stock/jobs.<br>- Support team workflows without locking resources. |
| Developer | - DB: User table links to Truck table (one-to-many; user can have one primary truck).<br>- UI: Table or cards for truck list, with assignment dropdowns.<br>- Multi-user locks: Prevent concurrent reassignments via transactions.<br>- Notifications: Alert on assignment changes. | - Simple linking for traceability.<br>- Handle offline changes (sync on reconnect if shared DB).<br>- Scale for small teams (10-20 users/trucks). |

#### Active Jobs Management
| Perspective | Features | Goals |
|-------------|----------|-------|
| User | - Active Jobs List: Personalized dashboard showing user's prioritized active jobs (e.g., sorted by deadline or assignment).<br>- Access restrictions: Only view/edit active jobs; inactive ones hidden or read-only.<br>- Multi-job support: Users can work on multiple active jobs (not locked), but prioritize their own.<br>- Team overlap: See if others are on the same job, with shared updates.<br>- Long-term jobs: Track progress over years, with activation/deactivation toggles. | - Focus users on relevant work without distractions.<br>- Enable collaboration on shared jobs.<br>- Handle multi-year electrical projects efficiently. |
| Developer | - DB: Jobs table with "active" flag, user assignments (many-to-many), and priority scores.<br>- Access control: Query filters by user + active status.<br>- UI: Dashboard with tabs for "My Active Jobs" vs. "All Active."<br>- Agents: LLM can suggest priority adjustments based on history. | - Enforce restrictions without complex auth.<br>- Efficient queries for large job histories.<br>- Integrate with truck assignments (e.g., link job to user's truck). |

#### Parts Consumption on Jobs
| Perspective | Features | Goals |
|-------------|----------|-------|
| User | - Quick consumption logging: From job view, select parts from truck stock and "consume" with one click (deducts from inventory, logs to job history).<br>- Easy tracking: Auto-update parts list as consumed; show remaining stock.<br>- Bundle support: Consume related parts together (e.g., wire + connectors).<br>- Alerts: Warn if consumption would deplete critical stock. | - Fast on-site recording for electricians.<br>- Accurate real-time inventory to prevent losses.<br>- Seamless integration with job flow (truck → job). |
| Developer | - Workflow: DB triggers on consumption (update stock, add log entry).<br>- UI: Mobile-like forms for quick entry (scan or dropdown).<br>- Validation: Check against truck assignment and active job.<br>- Offline: Queue logs for sync. | - Built-in to core logic for reliability.<br>- Quick performance (no heavy compute needed).<br>- Tie to audits for accuracy. |

#### LLM Background Agents for Administrative Tasks
| Perspective | Features | Goals |
|-------------|----------|-------|
| User | - Background automation: Agents run periodically (e.g., every hour) to check inconsistencies (e.g., "Parts consumed don't match stock changes").<br>- Notifications: Pop-up or in-app alerts for issues (e.g., "Audit reminder: Verify Truck #2 stock").<br>- Lookups/Adds: Agent can query info (e.g., "Find part alternatives") or add items (e.g., "Add new part card from description").<br>- Questions/Reminders: Prompt user for clarifications (e.g., "Confirm this return?") or remind of audits.<br>- Accuracy focus: Catch potential losses (e.g., unmatched consumptions) and suggest fixes. | - Hands-off management for admins/electricians.<br>- Proactive error catching for precise inventory.<br>- Easier than manual checks, especially for multi-user setups. |
| Developer | - Small Agents: Build 2-3 focused ones using repo's orchestration + local LLM.<br>  - Agent 1: Audit Agent (scans DB for mismatches; uses MCP tools like "query_stock" and "notify_user").<br>  - Agent 2: Admin Helper (handles lookups/adds; tools like "db_insert" and "prompt_user").<br>  - Agent 3: Reminder Agent (schedules audits/questions; tool for "schedule_task").<br>- Background: Run in threads/timers; low-priority to not block UI.<br>- Custom MCP Tools: Simple functions (e.g., DB wrappers) exposed to LLM via API-like calls.<br>- Config: Toggle frequency, enable/disable per user. | - Leverage LLM for fuzzy tasks (e.g., detecting "info that doesn't add up").<br>- Keep agents minimal (few tools) for speed on desktop.<br>- Secure: Tools only access DB, no external calls.<br>- Integrate with tickets for human-AI loop (e.g., flag issues as tickets). |

This enhances the system's usability for teams, with a focus on accuracy and automation. The LLM agents make complex admin tasks feasible without overcomplicating the code. If you need more on agent tools, UI sketches, or DB expansions, let me know!