"""일일 보고서를 파일로 만든다. 사용법: python -m app.report 2018-01-18"""
import argparse
from pathlib import Path

from .analysis import daily_report, report_markdown


def main() -> None:
    parser = argparse.ArgumentParser(description="일일 에너지 보고서 생성")
    parser.add_argument("date", help="YYYY-MM-DD")
    parser.add_argument("--out", default="reports", help="저장 폴더")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"energy-report-{args.date}.md"
    path.write_text(report_markdown(daily_report(args.date)) + "\n", encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
