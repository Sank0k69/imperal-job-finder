"""Side panels — left: saved jobs list, right: settings + CV."""
from __future__ import annotations

from imperal_sdk import ui
from app import ext, load_settings, load_cv, load_saved_jobs, cv_ready


# ──────────────────────────────────────────────────────
#  LEFT — Saved jobs
# ──────────────────────────────────────────────────────

@ext.panel(
    "sidebar",
    slot="left",
    title="Job Finder",
    icon="Briefcase",
    default_width=260,
    refresh="on_event:jobfinder.job.saved,jobfinder.results.ready,jobfinder.settings.saved",
)
async def panel_left(ctx):
    s     = await load_settings(ctx)
    cv    = await load_cv(ctx)
    saved = await load_saved_jobs(ctx)

    header = ui.Stack(direction="v", gap=2, children=[
        ui.Header(text="Job Finder", level=4),
        ui.Stack(direction="h", gap=2, children=[
            ui.Badge(
                label="CV ready" if cv_ready(cv) else "no CV",
                color="green" if cv_ready(cv) else "gray",
            ),
            *([] if not s.get("jsearch_key") else [
                ui.Badge(label="API connected", color="blue"),
            ]),
        ]),
    ])

    if not s.get("jsearch_key"):
        return ui.Stack(direction="v", gap=3, children=[
            header,
            ui.Divider(),
            ui.Alert(
                message="Add your JSearch API key in Settings (right panel) to get started.",
                type="warning",
            ),
        ])

    saved_section: list = []
    if saved:
        saved_section = [
            ui.Divider(),
            ui.Text(content="Saved jobs", variant="caption"),
            ui.List(items=[
                ui.ListItem(
                    id=j.get("job_id", str(i)),
                    title=(j.get("title", "")[:40] or "(no title)"),
                    subtitle=f"{j.get('company','')} — {j.get('location','')}",
                )
                for i, j in enumerate(saved[:20])
            ]),
        ]

    actions = ui.Stack(direction="v", gap=2, children=[
        ui.Divider(),
        ui.Form(action="search_jobs",  submit_label="Search now",   children=[]),
        ui.Form(
            action="search_jobs",
            submit_label="Remote only",
            children=[],
            defaults={"remote_only": True},
        ),
    ])

    return ui.Stack(direction="v", gap=3, children=[
        header,
        *saved_section,
        actions,
    ])


# ──────────────────────────────────────────────────────
#  RIGHT — Settings + CV
# ──────────────────────────────────────────────────────

@ext.panel(
    "settings",
    slot="right",
    title="Settings",
    icon="Settings",
    default_width=320,
    refresh="on_event:jobfinder.settings.saved,jobfinder.cv.saved",
)
async def panel_right(ctx):
    s  = await load_settings(ctx)
    cv = await load_cv(ctx)

    # API key + country
    api_form = ui.Section(
        title="JSearch API (RapidAPI)",
        children=[
            ui.Form(
                action="save_job_settings",
                submit_label="Save",
                children=[
                    ui.Input(
                        placeholder="RapidAPI key (JSearch)",
                        value=s.get("jsearch_key", ""),
                        param_name="jsearch_key",
                    ),
                    ui.Input(
                        placeholder="Country code (us, gb, de, ua…)",
                        value=s.get("country", "us"),
                        param_name="country",
                    ),
                ],
            ),
        ],
    )

    # Search filters
    type_opts = [
        {"value": "any",        "label": "Any"},
        {"value": "fulltime",   "label": "Full-time"},
        {"value": "parttime",   "label": "Part-time"},
        {"value": "contractor", "label": "Contract"},
        {"value": "intern",     "label": "Internship"},
    ]
    filter_form = ui.Section(
        title="Search Filters",
        collapsible=True,
        children=[
            ui.Form(
                action="save_job_settings",
                submit_label="Save filters",
                children=[
                    ui.Input(
                        placeholder="Location (e.g. London, Berlin)",
                        value=s.get("location", ""),
                        param_name="location",
                    ),
                    ui.Select(
                        options=type_opts,
                        value=s.get("job_type", "any"),
                        placeholder="Job type",
                        param_name="job_type",
                    ),
                    ui.Slider(
                        min=0, max=200000, step=5000,
                        value=int(s.get("salary_min") or 0),
                        label="Min salary (annual $)",
                        param_name="salary_min",
                    ),
                ],
            ),
        ],
    )

    # CV / profile section
    cv_source  = (cv.get("source") or "none") if cv else "none"
    cv_preview = ""
    if cv:
        raw = cv.get("content") or cv.get("description", "")
        cv_preview = (raw[:180] + "…") if len(raw) > 180 else raw

    cv_section = ui.Section(
        title="Your CV / Profile",
        children=[
            *([] if not cv_preview else [
                ui.Alert(message=f"Saved ({cv_source}): {cv_preview}", type="info"),
            ]),
            ui.Divider() if cv_preview else ui.Empty(message="No CV yet", icon="FileText"),
            ui.Text(content="Paste your CV:", variant="caption"),
            ui.Form(
                action="save_cv",
                submit_label="Save CV",
                children=[
                    ui.TextArea(
                        placeholder=(
                            "Paste your resume here (plain text or Markdown):\n"
                            "- Name, contact\n"
                            "- Work experience\n"
                            "- Skills\n"
                            "- Education\n"
                        ),
                        rows=8,
                        param_name="content",
                    ),
                ],
            ),
            ui.Divider(),
            ui.Text(content="Or describe yourself:", variant="caption"),
            ui.Form(
                action="describe_self",
                submit_label="Save description",
                children=[
                    ui.TextArea(
                        placeholder=(
                            "Tell Webbee about yourself:\n"
                            "- Your name and current role\n"
                            "- Years of experience and key skills\n"
                            "- What kind of work you're looking for\n"
                            "- Preferred location / remote\n"
                        ),
                        rows=6,
                        param_name="description",
                    ),
                ],
            ),
            *([] if not cv_ready(cv) else [
                ui.Form(
                    action="generate_cv",
                    submit_label="Generate polished CV",
                    children=[],
                ),
            ]),
        ],
    )

    return ui.Stack(direction="v", gap=4, children=[
        api_form,
        filter_form,
        cv_section,
    ])
