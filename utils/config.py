from pathlib import Path

import pandas as pd


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    file_path = project_root / "data" / "source" / "all_vm.xlsx"
    df = pd.read_excel(file_path)
    print(df.columns)


if __name__ == "__main__":
    main()
