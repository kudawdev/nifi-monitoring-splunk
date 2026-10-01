# Contributing

If you want to contribute to the development of this project, the best way
is a well structured and complete pull request, with tests and
documentation. Keep it focused: more than one thing in the same request makes
it harder to review.

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

These pages are bilingual: every `*.md` has an `*.es.md` counterpart, and a
change to one belongs in the other.

## Issues

If you found a bug or have a feature request you can register an issue. We always recommend reviewing the issues created, because it may be that it has already been reported.
