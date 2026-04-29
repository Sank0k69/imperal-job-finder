"""Main panel — AI-matched job results or empty state."""
from __future__ import annotations

from imperal_sdk import ui
from app import ext, load_settings, load_results, load_cv, cv_ready


MATCH_COLOR: dict = {
    range(80, 101): "green",
    range(60, 80):  "blue",
    range(40, 60):  "yellow",
    range(0,  40):  "red",
}


def _match_color(score: int) -> str:
    for r, c in MATCH_COLOR.items():
        if score in r:
            return c
    return "gray"


def _centered(children: list) -> ui.UINode:
    return ui.Stack(
        direction="v",
        align="center",
        className="min-h-full bg-muted/30 p-6",
        children=children,
    )


def _card(children: list, gap: int = 4) -> ui.UINode:
    return ui.Stack(
        direction="v",
        gap=gap,
        className="w-full max-w-3xl bg-background rounded-xl shadow-sm p-8",
        children=children,
    )


def _results_view(jobs: list) -> ui.UINode:
    cards = []
    for i, j in enumerate(jobs):
        n     = i + 1
        score = int(j.get("match_score", 0))
        remote = j.get("is_remote", False)

        cards.append(ui.Stack(
            direction="v",
            gap=2,
            className="border rounded-lg p-4 bg-card",
            children=[
                ui.Stack(direction="h", gap=2, align="center", children=[
                    ui.Badge(label=str(n), color="blue"),
                    ui.Badge(label=f"{score}% match", color=_match_color(score)),
                    *([] if not remote else [ui.Badge(label="remote", color="green")]),
                    ui.Text(content=j.get("title", ""), variant="body"),
                ]),
                ui.Stack(direction="h", gap=3, children=[
                    ui.KeyValue(label="Company",  value=j.get("company", "")),
                    ui.KeyValue(label="Location", value=j.get("location", "")),
                    *([] if not j.get("employment_type") else [
                        ui.KeyValue(label="Type", value=j["employment_type"]),
                    ]),
                    *([] if not j.get("salary") else [
                        ui.KeyValue(label="Salary", value=j["salary"]),
                    ]),
                ]),
                *([] if not j.get("snippet") else [
                    ui.Text(content=j["snippet"], variant="caption"),
                ]),
                *([] if not j.get("match_reason") else [
                    ui.Text(content=f"Match: {j['match_reason']}", variant="caption"),
                ]),
                ui.Stack(direction="h", gap=2, children=[
                    ui.Form(
                        action="apply_jobs",
                        submit_label=f"Apply {n}",
                        children=[],
                        defaults={"jobs": str(n), "max": 1},
                    ),
                    ui.Form(
                        action="save_job",
                        submit_label="Save",
                        children=[],
                        defaults={
                            "job_id":   j.get("job_id", ""),
                            "title":    j.get("title", ""),
                            "company":  j.get("company", ""),
                            "location": j.get("location", ""),
                            "url":      j.get("apply_url", ""),
                            "score":    score,
                        },
                    ),
                ]),
            ],
        ))

    return _centered([_card([
        ui.Stack(direction="h", gap=3, align="center", children=[
            ui.Header(
                text="Job Results",
                level=2,
                subtitle=f"{len(jobs)} matching positions",
            ),
            ui.Form(action="search_jobs", submit_label="Refresh", children=[]),
        ]),
        ui.Divider(),
        ui.Stack(direction="v", gap=4, children=cards),
        ui.Divider(),
        ui.Form(
            action="apply_jobs",
            submit_label="Apply to Top 5",
            children=[],
            defaults={"jobs": "all", "max": 5},
        ),
    ])])


def _empty_view(s: dict, cv: dict | None) -> ui.UINode:
    has_key = bool(s.get("jsearch_key"))
    has_cv  = cv_ready(cv)

    return _centered([_card([
        ui.Header(
            text="Job Finder",
            level=2,
            subtitle="Find jobs matched to your profile by AI",
        ),
        ui.Divider(),
        ui.Empty(message="No search results yet", icon="Briefcase"),
        *([] if has_cv else [
            ui.Alert(
                message="Add your CV in Settings or describe yourself to Webbee to enable AI matching.",
                type="warning",
            ),
        ]),
        *([] if has_key else [
            ui.Alert(
                message="Add your JSearch (RapidAPI) key in Settings to search across LinkedIn, Indeed and more.",
                type="info",
            ),
        ]),
        *([] if not (has_key and has_cv) else [
            ui.Form(action="search_jobs", submit_label="Search Jobs", children=[]),
        ]),
    ])])


@ext.panel(
    "main",
    slot="center",
    refresh="on_event:jobfinder.results.ready,jobfinder.cv.saved,jobfinder.settings.saved",
)
async def panel_main(ctx):
    s       = await load_settings(ctx)
    cv      = await load_cv(ctx)
    results = await load_results(ctx)

    if results:
        return _results_view(results)

    return _empty_view(s, cv)
