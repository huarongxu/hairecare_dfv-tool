"""
DFV History Manager
===================
Interactively list and DELETE historical DFV runs from the database,
then regenerate the dashboard.

Usage:
    python dfv_tool/manage_history.py          # interactive menu
    python dfv_tool/manage_history.py --list   # just list runs

In the interactive menu you can delete duplicate/unwanted weeks
(e.g. a repeated W24/2026 or W22/2026) by typing their numbers.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from history import get_all_runs, get_errors_for_run, delete_runs


def _print_table(runs):
    print()
    print(f"  {'#':>3}  {'ID':>4}  {'Week':>10}  {'Run Date':<16}  {'Rows':>7}  {'Errors':>6}  {'Diff%':>7}")
    print("  " + "-" * 70)
    for i, r in enumerate(runs, 1):
        diff = f"{r['diff_pct']:.2f}" if r.get('diff_pct') is not None else "?"
        print(f"  {i:>3}  {r['id']:>4}  {r['week_label'] or '?':>10}  "
              f"{(r['run_date'] or ''):<16}  {r['total_rows'] or 0:>7}  "
              f"{r['total_errors'] or 0:>6}  {diff:>7}")
    print()


def _parse_selection(text, n):
    """Parse '1,3,5' or '2-4' or '1 3 6' into a set of 1-based indices."""
    picks = set()
    for token in text.replace(",", " ").split():
        token = token.strip()
        if "-" in token:
            a, b = token.split("-", 1)
            if a.isdigit() and b.isdigit():
                for k in range(int(a), int(b) + 1):
                    if 1 <= k <= n:
                        picks.add(k)
        elif token.isdigit():
            k = int(token)
            if 1 <= k <= n:
                picks.add(k)
    return sorted(picks)


def _regenerate_dashboard():
    try:
        from dashboard import generate_dashboard
        path = generate_dashboard()
        if path:
            print(f"  Dashboard regenerated: {path}")
    except Exception as e:
        print(f"  [WARN] Could not regenerate dashboard: {e}")


def main():
    list_only = "--list" in sys.argv

    runs = get_all_runs()
    if not runs:
        print("No runs in history database.")
        return

    print("\n=== DFV History ===")
    _print_table(runs)

    if list_only:
        return

    print("Enter the # of the run(s) to DELETE (e.g. '1' or '1,3' or '2-4').")
    print("Press Enter to cancel.")
    sel = input("Delete which #: ").strip()
    if not sel:
        print("Cancelled. Nothing deleted.")
        return

    picks = _parse_selection(sel, len(runs))
    if not picks:
        print("No valid selection. Nothing deleted.")
        return

    chosen = [runs[i - 1] for i in picks]
    print("\nYou are about to DELETE these runs:")
    for r in chosen:
        print(f"  - #{r['id']}  {r['week_label']}  {r['run_date']}  "
              f"({r['total_errors'] or 0} errors)")

    confirm = input(f"\nType 'yes' to permanently delete {len(chosen)} run(s): ").strip().lower()
    if confirm != "yes":
        print("Cancelled. Nothing deleted.")
        return

    ids = [r["id"] for r in chosen]
    n_runs, n_errors = delete_runs(ids)
    print(f"\nDeleted {n_runs} run(s) and {n_errors} error row(s).")

    _regenerate_dashboard()

    remaining = get_all_runs()
    if remaining:
        print("\n=== Remaining History ===")
        _print_table(remaining)
    else:
        print("\nHistory is now empty.")


if __name__ == "__main__":
    main()
