import os
import argparse
import subprocess


MAIN = """from prospector import dig
dig("x")
"""


def parse_args():
    p = argparse.ArgumentParser(description="Script to print Prospector's graph. You need `graphviz` installed, "
                                            "refer to https://www.bonobo-project.org/how-to/inspect-an-etl-jobs-graph")

    p.add_argument("--tmp-file", type=str, help="Path of the tmp file for the main.", default="/tmp/main.py")
    p.add_argument("--img", type=str, help="Path of the image file to save.", default="./graph.png")

    args = p.parse_args()
    return args


def main(args):
    # Write tmp main
    with open(args.tmp_file, 'w') as f:
        f.write(MAIN)

    # Execute Bonobo inspect
    cmd_inspect = ['bonobo', 'inspect', '--graph', args.tmp_file]
    cmd_save = ['dot', '-o', args.img, '-T', 'png']
    out = subprocess.run(cmd_inspect, stdout=subprocess.PIPE)
    out = subprocess.run(cmd_save, input=out.stdout)
    assert out.returncode == 0, "Failed to generate graph."

    # Delete tmp main
    os.remove(args.tmp_file)

    print("Graph saved in : {}".format(args.img))


if __name__ == "__main__":
    main(parse_args())
