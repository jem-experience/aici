import subprocess
import ujson
import sys
import os

import pyaici.ast as ast
import pyaici.rest
import pyaici.util


def upload_wasm(prog="aici_ast_runner"):
    r = subprocess.run(["sh", "wasm.sh", "build"], cwd=prog)
    if r.returncode != 0:
        sys.exit(1)
    file_path = prog + "/target/opt.wasm"
    return pyaici.rest.upload_module(file_path)


def ask_completion(*args, **kwargs):
    res = pyaici.rest.completion(*args, **kwargs)
    print("\n[Prompt] " + res["request"]["prompt"] + "\n")
    for text in res["text"]:
        print("[Response] " + text + "\n")
    os.makedirs("tmp", exist_ok=True)
    path = "tmp/response.json"
    with open(path, "w") as f:
        ujson.dump(res, f, indent=1)
    print(f"response saved to {path}")
    print(res["storage"])


def main():
    arg = {
        "steps": [ast.fixed("Here's some JSON about J.R.Hacker from Seattle:\n")]
        + ast.json_to_steps(
            {
                "name": "",
                "valid": True,
                "description": "",
                "type": "foo|bar|baz|something|else",
                "address": {"street": "", "city": "", "state": "[A-Z][A-Z]"},
                "age": 1,
                "fraction": 1.5,
            }
        )
    }
    _arg = {
        "steps": [
            ast.fixed(" French is", tag="lang"),
            ast.gen(max_tokens=5, mask_tags=["lang"]),
        ]
    }
    _arg = {
        "steps": [
            ast.fixed("Please answer the following questions:"),
            ast.fixed("(And answer in ALL CAPS):", tag="allcaps"),
            ast.fixed("\n Q: Who is the president of the USA?\n A:"),
            ast.gen(max_tokens=10, mask_tags=["allcaps"]),
            ast.fixed("\\n Q: And who is the vice president?\n A:"),
            ast.gen(max_tokens=20, mask_tags=["allcaps"]),
            ast.fixed("\nPlease give a url with evidence\n http://"),
            ast.gen(max_tokens=20),
        ]
    }
    _arg = {
        "steps": [
            ast.fixed("The word 'hello' in"),
            ast.fork(
                [
                    ast.wait_vars("french", "spanish"),
                    ast.fixed(
                        "\nfrench:{{french}}\nspanish:{{spanish}}\n", expand_vars=True
                    ),
                ],
                [
                    ast.fixed(" Spanish is"),
                    ast.gen(rx=r" '[^']*'", max_tokens=15, set_var="spanish"),
                ],
                [
                    ast.fixed(" French is"),
                    ast.gen(rx=r" '[^']*'", max_tokens=15, set_var="french"),
                ],
            ),
        ]
    }

    _arg = {
        "steps": [
            ast.fixed("The word 'hello'"),
            ast.label("lang", ast.fixed(" in French is translated as")),
            ast.gen(rx=r" '[^']*'", max_tokens=15, set_var="french"),
            ast.fixed(" or", following="lang"),
            ast.gen(rx=r" '[^']*'", max_tokens=15, set_var="blah"),
            ast.fixed("\nResults: {{french}} {{blah}}", expand_vars=True),
        ]
    }

    notes = "The patient should take some tylenol in the evening and aspirin in the morning. They should also take something for indigestion.\n"
    notes = "Start doctor note:\n" + notes + "\nEnd doctor note.\n"

    _arg = {
        "steps": [
            ast.fixed("[INST] "),
            # there is currently a bug going back to the first token, so we label the stuff after [INST] instead
            ast.label(
                "start",
                ast.fixed(
                    "List drug names in the following doctor's notes. Use <drug>Drug Name</drug> syntax. Say DONE when done. [/INST]\n"
                    + notes
                ),
            ),
            ast.gen(
                max_tokens=100,
                stop_at="DONE",
                set={
                    "drugs": ast.e_extract_all(r"<drug>([^<]*</drug>)", ast.e_current())
                },
            ),
            ast.fixed(
                "For each drug in the following doctor's notes give the time to take it. "
                "Use <drug>Drug Name</drug> syntax when referring to any drugs. [/INST]\n"
                + notes,
                following="start",
            ),
            ast.gen(
                max_tokens=100,
                inner={
                    "<drug>": ast.e_var("drugs"),
                },
            ),
        ]
    }

    _arg = {
        "prompt": "The word 'hello'",
        "steps": [
            ast.fixed(" in French is"),
            ast.gen(max_tokens=5),
        ],
    }

    _arg = {
        "steps": [
            ast.fixed("I am about "),
            ast.gen(max_tokens=5, rx=r"\d+"),
            ast.fixed(" years and "),
            ast.gen(max_tokens=5, rx=r"\d+"),
            ast.fixed(" months."),
        ]
    }

    _arg = {
        "steps": [
            ast.fixed("Please remember the following items:\nFoo\nZzzzz"),
            ast.label("l", ast.fixed("\nBar\nBaz")),
            ast.fixed("\nPlease repeat the list, say DONE when done:\n"),
            ast.gen(max_tokens=20, stop_at="DONE", set_var="x"),
            ast.fixed(
                "\nQux\nMux\nPlease repeat the list, say DONE when done:\n",
                following="l",
            ),
            ast.gen(max_tokens=20, stop_at="DONE", set_var="y"),
        ],
    }

    if len(sys.argv) > 1 and sys.argv[1].endswith(".txt"):
        pyaici.rest.log_level = 2
        prompt = open(sys.argv[1]).read()
        ask_completion(
            prompt=prompt,
            aici_module=None,
            aici_arg=None,
            ignore_eos=True,
            max_tokens=10,
        )
        return

    if len(sys.argv) > 1 and sys.argv[1].endswith(".py"):
        mod = upload_wasm("pyvm")
        pyaici.rest.log_level = 2
        arg = open(sys.argv[1]).read()
        ask_completion(
            prompt="",
            aici_module=mod,
            aici_arg=arg,
            ignore_eos=True,
        )
        return

    mod = upload_wasm()
    pyaici.rest.log_level = 1
    # read file named on command line if provided
    wrap = pyaici.util.codellama_prompt
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        with open(sys.argv[1]) as f:
            arg = ujson.load(f)
        ask_completion(
            prompt=wrap(arg["prompt"]),
            aici_module=mod,
            aici_arg=arg,
            **arg["sampling_params"],
        )
    else:
        ask_completion(
            prompt=arg.get("prompt", ""),
            # prompt=wrap("Write fib function in C, respond in code only"),
            aici_module=mod,
            aici_arg=arg,
            n=1,
            temperature=0,
            max_tokens=200,
        )


main()
