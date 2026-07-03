import json

from scripts.run_pipeline_funnel_report import collect_metrics, main, render_markdown


def test_funnel_report_marks_legacy_batches_without_metrics_as_na(tmp_path, capsys):
    with_metrics = tmp_path / "idea_batch_with_metrics"
    without_metrics = tmp_path / "idea_batch_without_metrics"
    with_metrics.mkdir()
    without_metrics.mkdir()
    (with_metrics / "funnel_metrics.json").write_text(
        json.dumps(
            {
                "batch_id": "idea_batch_with_metrics",
                "driver": "literature",
                "fetched": 2,
                "scored": 2,
                "above_threshold": 1,
                "selected": 1,
            }
        ),
        encoding="utf-8",
    )

    rows = collect_metrics(tmp_path)
    table = render_markdown(rows)

    assert rows[0]["missing_metrics"] is False
    assert rows[1]["missing_metrics"] is True
    assert "| idea_batch_with_metrics | literature | 2 | 2 | 1 | 1 | n/a | n/a | n/a |" in table
    assert "| idea_batch_without_metrics | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |" in table

    assert main(["--results-root", str(tmp_path)]) == 0
    stdout = capsys.readouterr().out
    assert "idea_batch_without_metrics" in stdout
