use anyhow::Result;
use derivre::{RegexVec, StateID};

mod common;
use common::RegexTests;
use hashbrown::HashSet;

fn suite() -> Result<RegexTests> {
    let mut tests = RegexTests::new();
    macro_rules! load {
        ($name:expr) => {{
            const DATA: &[u8] = include_bytes!(concat!("./", $name, ".toml"));
            tests.load_slice($name, DATA)?;
        }};
    }
    load!("fowler-basic");
    Ok(tests)
}

#[test]
fn test_fowler() {
    let disabled = vec![3, 18, 20, 21, 22, 23, 90, 91, 92, 110, 140, 141];
    let disabled: HashSet<_> = disabled
        .iter()
        .map(|n| format!("fowler-basic/basic{}", n))
        .collect();

    let data = suite().unwrap();
    for t in &data.tests {
        if disabled.contains(&t.full_name) {
            println!("skipping disabled test: {}", t.full_name);
            continue;
        }
        println!("test: {} {:?}", t.full_name, t.regex);

        let parser = regex_syntax::ParserBuilder::new()
            .case_insensitive(t.case_insensitive)
            // .dot_matches_new_line(false)
            // .unicode(false)
            // .utf8(false)
            .build();

        let parsed = RegexVec::new_with_parser(parser, &[&t.regex]);
        if parsed.is_err() {
            panic!(
                "invalid syntax {} {:?}; {}",
                t.full_name,
                t.regex,
                parsed.err().unwrap()
            );
        }

        let mut rx = parsed.unwrap();
        let mut matches = vec![];

        // find all leftmost-longest matches
        for start_idx in 0..t.haystack.len() {
            let mut state = rx.initial_state_all();
            let mut last_match = if rx.state_desc(state).is_accepting() {
                start_idx as isize
            } else {
                -1
            };
            for idx in start_idx..t.haystack.len() {
                let c = t.haystack[idx];
                let new_state = rx.transition(state, c);
                if rx.state_desc(new_state).is_accepting() {
                    last_match = (idx + 1) as isize;
                }
                if new_state == StateID::DEAD {
                    break;
                }
                state = new_state;
            }
            if last_match >= 0 {
                matches.push(vec![start_idx, last_match as usize]);
                if matches.len() >= t.match_limit.unwrap_or(usize::MAX) {
                    break;
                }
            }
        }

        let expected = t.matches.iter().map(|m| m[0].clone()).collect::<Vec<_>>();

        if expected != matches {
            panic!(
                "mismatched matches for: {}, expected: {:?}, got: {:?}",
                t.full_name, expected, matches
            );
        }
    }
}
