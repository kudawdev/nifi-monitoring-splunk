# Contributing

Thank you for your interest in our content, if you want to contribute to the development of this project the best way to do it is by sending a well structured and complete Pull Request, with tests and documentation. Try to be focused, doing more than one thing in a single request will make it harder to process.

## Running the tests

The add-on is generated, so the first step is building it. Nothing else needs
installing: the unit tests use the standard library only, and the integration
environment needs Docker and nothing more.

```
./tests/build-ta.sh
cd tests/unit && python3 -m unittest discover -v
```

The integration harness brings up NiFi and Splunk in containers and checks
that data actually arrives and that the fields come out. It covers ten
scenarios — every supported NiFi version and architecture, against both ways
of getting data out of NiFi:

```
cd tests
./run.sh --list                 # the scenarios
./run.sh --list cluster         # everything about one of them
./run.sh nifi2-current          # bring it up, assert, tear down
```

`run.sh` exits non-zero if anything fails, and tears the stack down
afterwards. `--keep` leaves it running so you can look around, and `--bare`
brings up the machines without installing anything, which is how to exercise
the installation itself.

A pull request does not need the whole matrix. Run the unit tests, plus the
one scenario closest to what you changed — `./run.sh --list` says what each
one covers. CI runs four scenarios on a pull request and all ten on a
release.

There is more detail, including the known rough edges of the environment, in
[`tests/README.md`](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/tests/README.md).

## Documentation

These pages are bilingual: every `*.md` has an `*.es.md` counterpart, and a
change to one belongs in the other.

## Issues

If you found a bug or have a feature request you can register an issue. We always recommend reviewing the issues created, because it may be that it has already been reported.
