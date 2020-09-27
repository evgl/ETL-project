import os
import pathlib
from difflib import SequenceMatcher

from prospector import pumpjack


DATA_DIR = 'data'
REF_DIR = 'ref'
PRED_DIR = 'pred'

RESULT_FILE = "/tmp/benchmark.md"


def get_files_names():
    cur_dir = pathlib.Path(__file__).parent.absolute()
    data_dir = os.path.join(cur_dir, DATA_DIR)
    ref_dir = os.path.join(cur_dir, REF_DIR)
    pred_dir = os.path.join(cur_dir, PRED_DIR)

    # Get the name of the files without extension
    files = [os.path.splitext(f)[-2] for f in os.listdir(data_dir)]

    pdf_files = [os.path.join(data_dir, "{}.pdf".format(f)) for f in files]
    ref_files = [os.path.join(ref_dir, "{}.html".format(f)) for f in files]
    pred_files = [os.path.join(pred_dir, "{}.html".format(f)) for f in files]
    return pdf_files, ref_files, pred_files, pred_dir


def get_scores(ref_files, pred_files):
    scores = []
    for ref, pred in zip(ref_files, pred_files):
        with open(ref) as r, open(pred) as p:
            html_ref = r.read()
            html_pred = p.read()

        m = SequenceMatcher(None, html_ref, html_pred)
        scores.append(m.ratio())
    return scores


def print_scores(scores, files):
    assert len(scores) == len(files)
    print("\n========= Scores =========\n")
    for s, f in zip(scores, files):
        print("{} = {:.4f}".format(os.path.basename(f), s))
    print("\n==========================")


def write_scores_table(scores, files):
    md = "| File | Score |\n|----------:|:-------|\n"
    for s, f in zip(scores, files):
        if int(s) == 100:
            md += "| {} | **✅** |\n".format(os.path.basename(f))
        else:
            md += "| {} | **{}** |\n".format(os.path.basename(f), int(s))

    with open(RESULT_FILE, 'w') as f:
        f.write(md)


def main():
    pdf_files, ref_files, pred_files, pred_dir = get_files_names()

    pumpjack(pdf_files, directory=pred_dir)

    print("Computing scores...")
    scores = get_scores(ref_files, pred_files)
    scores = [s * 100 for s in scores]

    print_scores(scores, pdf_files)
    write_scores_table(scores, pdf_files)


if __name__ == "__main__":
    main()
