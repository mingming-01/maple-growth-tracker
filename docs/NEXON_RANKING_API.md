# Nexon MapleStory ranking API contract

Verified against the live API on 2026-11-09 using the key from the local
environment. The key, OCID, and character name are not stored here.

## Confirmed request behavior

| Request | Result |
| --- | --- |
| `ranking/overall?date=2026-11-08&world_type=0&page=1` | HTTP 200, 200 rows; each row includes `ranking`, `class_name`, `sub_class_name`, and `world_name`. |
| Same query with `class=<class_name>-<sub_class_name>` | HTTP 200, 200 rows; all rows on the returned page had the requested job. `ranking` started at 1. |
| Same query with `character_class=<class_name>-<sub_class_name>` | HTTP 200, 200 rows containing multiple jobs. The parameter was ignored. |
| Same query with `class=<sub_class_name>` only | HTTP 400, `OPENAPI00004`. |
| `class`, `world_name`, and a valid `ocid` together | HTTP 200, one matching row with its filtered rank. |
| `world_type=1&page=1` | HTTP 200, 200 rows from Eos/Helios worlds. |
| OCID lookup for a sample Eos character with `world_type=0` / `1` | Type 0 returned no row; type 1 returned one matching row. |
| `class`, `world_name`, `ocid`, and `world_type=1` together | HTTP 200, one matching row. |

The confirmed filter key is `class`. Its value is the response's
`<class_name>-<sub_class_name>`, for example `프렌즈 월드-키네시스`. The
response-derived value should be preferred; `static/jobs.json` remains a
fallback if those fields are absent.

The OCID combination allows direct lookup of the target's rank within the
filtered list. The service therefore makes one overall OCID lookup to obtain
the class metadata, then fetches world and job ranks with three concurrent
requests. This is four ranking requests total; the first request is a
dependency, so all four cannot start at the same time without using a static
job map in place of the API response.

## World type

At verification time, `world_type=1` returned Eos and Helios rows. Nexon's
notice says the former Reboot worlds became Eos and Helios. The app maps those
names (and historical Reboot names) to type 1 and other worlds to type 0.
[Nexon notice](https://m.maplestory.nexon.com/News/Notice/144849)

## Sanitized fixture

`tests/fixtures/nexon_ranking_filtered_sample.json` contains a reduced response
shape with all personal identifiers removed. It records only fields needed to
test filter validation.

## Limits of this verification

The live probe verified the parameter key, composite value, filtered ranking,
OCID combination, and current Eos/type-1 behavior. It did not exhaustively
probe every job name, every malformed value, historical date readiness, or all
worlds. The fixture is sanitized and does not contain the original response
body.
