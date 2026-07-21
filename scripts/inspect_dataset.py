"""Inspect the frozen CUAVerifierBench split without exposing labels."""

from cuav_data import load_frozen_split


def main() -> None:
    dataset = load_frozen_split()

    print("rows:", len(dataset))
    print("columns:", dataset.column_names)

    for index in range(min(3, len(dataset))):
        row = dataset[index]
        print("=" * 80)
        print("index:", index)
        print("task_id:", row.get("task_id"))
        print("instruction:", row.get("instruction"))
        print("init_url:", row.get("init_url"))
        print("screenshots:", len(row.get("screenshots") or []))
        print("has log:", bool(row.get("web_surfer_log")))
        print("final answer:", row.get("final_answer"))


if __name__ == "__main__":
    main()
