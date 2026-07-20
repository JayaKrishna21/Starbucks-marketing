from . import apify_ig, sheets_client, gemini_classify, config


def run():
    print(f"Scraping hashtags {config.HASHTAGS} and intersecting...")
    matched_posts = apify_ig.get_posts_with_both_hashtags()
    print(f"Found {len(matched_posts)} posts containing ALL hashtags.")

    if not matched_posts:
        print("No matched posts this run. Nothing to do.")
        return

    print("Checking Google Sheet for already-processed post IDs...")
    existing_ids = sheets_client.get_existing_post_ids()
    new_posts = [p for p in matched_posts if str(p["post_id"]) not in existing_ids]
    skipped = len(matched_posts) - len(new_posts)
    print(f"{len(new_posts)} new posts to process ({skipped} already logged, skipped).")

    if not new_posts:
        print("Nothing new since last run.")
        return

    print("Pulling comments for new posts...")
    enriched = apify_ig.enrich_with_comments(new_posts)

    print("Classifying each post with Gemini...")
    processed_rows = []
    for post in enriched:
        verdict = gemini_classify.classify_post(post["caption"], post["comments"])
        row = {**post, **verdict}
        processed_rows.append(row)
        print(f"  {post['post_id']}: {verdict['demand_signal']} "
              f"({verdict.get('product_requested')})")

    print("Writing raw log (all posts, yes and no)...")
    sheets_client.append_raw_log(processed_rows)

    yes_rows = [r for r in processed_rows if r["demand_signal"] == "yes"]
    print(f"{len(yes_rows)} of {len(processed_rows)} posts showed a demand signal.")

    if yes_rows:
        print("Rebuilding rollup tab from all 'yes' records in the sheet...")
        # Rollup should reflect the FULL history of yes-rows, not just this run,
        # so we re-read the raw log after writing and rebuild from everything logged.
        all_existing = _read_all_yes_rows_from_log()
        sheets_client.write_rollup(all_existing)
    else:
        print("No demand signals this run; rollup left unchanged.")

    print("Done.")


def _read_all_yes_rows_from_log() -> list:
    """Re-reads the raw_log tab so the rollup reflects full history, not just this run."""
    sheet = sheets_client._get_sheet()
    ws = sheet.worksheet(config.RAW_LOG_TAB)
    records = ws.get_all_records()
    return [r for r in records if r.get("demand_signal") == "yes"]


if __name__ == "__main__":
    run()