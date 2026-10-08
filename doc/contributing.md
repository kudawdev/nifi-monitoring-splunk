# Contributing

Nifi Monitoring is open source, under the
[MIT license](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/LICENSE),
and maintained by [Küdaw](about.md). Bug reports, fixes, new endpoints and
documentation are all welcome.

## Pull requests

Open them against `main`. The best pull request is a focused one, with tests
and documentation: more than one thing in the same request makes it harder
to review. Before you open it:

- Run the unit tests, and the integration scenario closest to what you
  changed (below).
- If you touched user-facing behaviour, update the docs in both languages.
- If you added a NiFi endpoint, follow the checklist in
  [`AGENTS.md`](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/AGENTS.md):
  the endpoint list, the sourcetype routing and the input form go together.

By contributing you agree that your contribution is licensed under the MIT
license, like the rest of the project.

## Running the tests

The add-on is generated, so the first step is building it. You need Docker
and Python 3, and network access the first time: the build installs
`ucc-gen` from PyPI into a virtualenv of its own. The unit tests use the
standard library only.

```
./tests/build-ta.sh
cd tests/unit && python3 -m unittest discover -v
```

The integration harness brings up NiFi and Splunk in containers and checks
that data actually arrives and that the fields come out. It covers ten
scenarios — NiFi 1.23.2, 1.28.1, 2.0.0 and 2.11.0, standalone, multi-instance
and cluster, across both ways of getting data out of NiFi:

```
cd tests
./run.sh --list                 # the scenarios
./run.sh --list cluster         # everything about one of them
./run.sh nifi2-current          # bring it up, assert, tear down
```

`run.sh` exits non-zero if anything fails, and tears the stack down
afterwards. `--keep` leaves it running so you can look around, and `--bare`
brings up the machines without installing anything, which is how to exercise
the installation itself; it leaves them running too.

`make check` runs the lint, the unit tests, AppInspect and the integration
scenarios in the same image CI uses; `make integration` runs only the
scenarios.

A pull request does not need the whole matrix. Run the unit tests, plus the
one scenario closest to what you changed — `./run.sh --list` says what each
one covers. CI runs by hand, not on every pull request: the dev and testing
workflows run four scenarios, and the release workflow all ten.

There is more detail, including the known rough edges of the environment, in
[`tests/README.md`](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/tests/README.md).

## Documentation

These pages live in `doc/` and are built with MkDocs. To preview them while
you edit:

```
pip install -r doc/requirements.txt
mkdocs serve      # http://127.0.0.1:8000/nifi-monitoring-splunk/
```

They are bilingual: every `*.md` has an `*.es.md` counterpart, and a change to
one belongs in the other. A new page goes in the `nav` of `mkdocs.yml` and in
the `llmstxt` sections, which is how agents find it; the unit tests fail if
any of the three is missing.

## Issues

Found a bug or missing something? Check the
[existing issues](https://github.com/kudawdev/nifi-monitoring-splunk/issues)
first — it may already be reported — and otherwise
[open a new one](https://github.com/kudawdev/nifi-monitoring-splunk/issues/new).
A bug report is much faster to act on with:

- The versions: both apps, NiFi and Splunk.
- How data gets in: pull or push, and standalone, several instances or a
  cluster.
- What you expected and what happened instead — the panel, the search, or
  the error on screen.
- On pull, the add-on's own log:
  `index=_internal sourcetype=splunkd component=ExecProcessor "nifi.py"` around the time of the problem.

For an evaluation, a deployment, or help running the apps, write to
splunk.app@kudaw.com — see [About Küdaw](about.md).
