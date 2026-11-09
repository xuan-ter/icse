# Symbolized WSL perf hot paths

Top sampled user-space addresses are resolved against the exact four-cell binaries used for capture.
Entries are sampled CPU-cycle evidence; they identify candidate executed functions, not causal compiler mechanisms.

## ripgrep

| Cell | Rank | Samples | Self % | Address | Function | Location |
|---|---:|---:|---:|---|---|---|
| 00 | 1 | 121 | 4.62 | `0x000000000018afdb` | `encoding_rs_io::DecodeReaderBytes<R,B>::fill` | `symbol-table` |
| 00 | 2 | 121 | 3.04 | `0x0000000000375573` | `memchr::arch::generic::packedpair::Finder<V>::find` | `memchr::arch::generic::packedpair::Finder<V>::find at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/memchr-2.7.6/src/arch/generic/packedpair.rs:85 |  (inlined by) memchr::arch::x86_64::avx2::packedpair::Finder::find_impl at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/memchr-2.7.6/src/arch/x86_64/avx2/packedpair.rs:156` |
| 00 | 3 | 121 | 3.04 | `0x0000000000374644` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/aho-corasick-1.1.3/src/packed/teddy/generic.rs:53` |
| 00 | 4 | 121 | 2.39 | `0x00000000003745f9` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/aho-corasick-1.1.3/src/packed/teddy/generic.rs:59` |
| 00 | 5 | 121 | 2.27 | `0x00000000003740c8` | `aho_corasick::nfa::contiguous::State::kind` | `aho_corasick::nfa::contiguous::State::kind at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/aho-corasick-1.1.3/src/nfa/contiguous.rs:553 |  (inlined by) aho_corasick::nfa::contiguous::State::match_len at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/aho-corasick-1.1.3/src/nfa/contiguous.rs:584 |  (inlined by) <aho_corasick::nfa::contiguous::NFA as aho_corasick::automaton::Automaton>::match_len at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/aho-corasick-1.1.3/src/nfa/contiguous.rs:297` |
| 00 | 6 | 121 | 2.17 | `0x00000000001787c7` | `grep_searcher::line_buffer::LineBuffer::fill` | `symbol-table` |
| 00 | 7 | 121 | 1.95 | `0x000000000018b0b5` | `encoding_rs_io::DecodeReaderBytes<R,B>::fill` | `symbol-table` |
| 00 | 8 | 121 | 1.74 | `0x00000000002047f7` | `<&mut S as grep_searcher::sink::Sink>::finish` | `symbol-table` |
| 00 | 9 | 121 | 1.71 | `0x0000000000177997` | `grep_printer::standard::StandardSink<M,W>::record_matches` | `symbol-table` |
| 00 | 10 | 121 | 1.68 | `0x000000000018afa8` | `encoding_rs_io::DecodeReaderBytes<R,B>::fill` | `symbol-table` |
| 00 | 11 | 121 | 1.64 | `0x000000000037464c` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 00 | 12 | 121 | 1.63 | `0x00000000001787d2` | `grep_searcher::sink::SinkError::error_config` | `symbol-table` |
| 00 | 13 | 121 | 1.50 | `0x000000000029c5c2` | `<&A as regex_automata::dfa::automaton::Automaton>::match_pattern` | `symbol-table` |
| 00 | 14 | 121 | 1.47 | `0x00000000003745f5` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 00 | 15 | 121 | 1.40 | `0x0000000000374603` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 00 | 16 | 121 | 1.36 | `0x0000000000178810` | `grep_searcher::sink::SinkError::error_config` | `symbol-table` |
| 00 | 17 | 121 | 1.36 | `0x000000000023e9b0` | `ryu::pretty::format64` | `symbol-table` |
| 00 | 18 | 121 | 1.31 | `0x0000000000374593` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 00 | 19 | 121 | 1.26 | `0x0000000000178815` | `grep_searcher::sink::SinkError::error_config` | `symbol-table` |
| 00 | 20 | 121 | 1.24 | `0x000000000018b071` | `encoding_rs_io::DecodeReaderBytes<R,B>::fill` | `symbol-table` |
| 00 | 21 | 121 | 1.19 | `0x0000000000374870` | `<aho_corasick::util::prefilter::Memmem as aho_corasick::util::prefilter::PrefilterI>::find_in` | `symbol-table` |
| 00 | 22 | 121 | 1.11 | `0x0000000000178628` | `grep_searcher::line_buffer::LineBuffer::fill` | `symbol-table` |
| 00 | 23 | 121 | 1.11 | `0x00000000003745cf` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 00 | 24 | 121 | 1.09 | `0x000000000029c5df` | `<&A as regex_automata::dfa::automaton::Automaton>::next_eoi_state` | `symbol-table` |
| 00 | 25 | 121 | 1.09 | `0x00000000003772d9` | `memchr::arch::x86_64::memchr::memrchr3_raw::find_avx2` | `symbol-table` |
| 00 | 26 | 121 | 1.08 | `0x00000000002046ea` | `<&mut S as grep_searcher::sink::Sink>::finish` | `symbol-table` |
| 00 | 27 | 121 | 1.08 | `0x000000000018b0a6` | `encoding_rs_io::DecodeReaderBytes<R,B>::fill` | `symbol-table` |
| 00 | 28 | 121 | 1.07 | `0x0000000000374173` | `<aho_corasick::packed::teddy::generic::Teddy<_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 00 | 29 | 121 | 1.07 | `0x000000000018aff4` | `encoding_rs_io::DecodeReaderBytes<R,B>::fill` | `symbol-table` |
| 00 | 30 | 121 | 1.05 | `0x00000000003746d3` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 10 | 1 | 99 | 4.13 | `0x00000000003745f9` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/aho-corasick-1.1.3/src/packed/teddy/generic.rs:59` |
| 10 | 2 | 99 | 3.56 | `0x0000000000374112` | `<aho_corasick::packed::teddy::generic::Teddy<_> as core::fmt::Debug>::fmt` | `<aho_corasick::packed::teddy::generic::Teddy<_> as core::fmt::Debug>::fmt at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/aho-corasick-1.1.3/src/packed/teddy/generic.rs:727` |
| 10 | 3 | 99 | 2.68 | `0x0000000000178628` | `grep_searcher::line_buffer::LineBuffer::fill` | `symbol-table` |
| 10 | 4 | 99 | 2.54 | `0x0000000000374590` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/aho-corasick-1.1.3/src/packed/teddy/generic.rs:53` |
| 10 | 5 | 99 | 2.33 | `0x000000000037466f` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/aho-corasick-1.1.3/src/packed/teddy/generic.rs:53` |
| 10 | 6 | 99 | 2.30 | `0x000000000037417b` | `<aho_corasick::packed::teddy::generic::Teddy<_> as core::fmt::Debug>::fmt` | `<aho_corasick::packed::teddy::generic::Teddy<_> as core::fmt::Debug>::fmt at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/aho-corasick-1.1.3/src/packed/teddy/generic.rs:732` |
| 10 | 7 | 99 | 2.28 | `0x0000000000374726` | `<aho_corasick::packed::teddy::builder::x86_64::FatAVX2<_> as core::fmt::Debug>::fmt` | `<aho_corasick::packed::teddy::builder::x86_64::FatAVX2<_> as core::fmt::Debug>::fmt at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/aho-corasick-1.1.3/src/packed/teddy/builder.rs:600` |
| 10 | 8 | 99 | 1.81 | `0x000000000037416b` | `<aho_corasick::packed::teddy::generic::Teddy<_> as core::fmt::Debug>::fmt` | `<aho_corasick::packed::teddy::generic::Teddy<_> as core::fmt::Debug>::fmt at aho_corasick.767c51d147f47206-cgu.0:?` |
| 10 | 9 | 99 | 1.80 | `0x000000000023e9bf` | `ryu::pretty::format64` | `symbol-table` |
| 10 | 10 | 99 | 1.78 | `0x0000000000375d5e` | `memchr::arch::x86_64::avx2::memchr::Two::find_raw` | `symbol-table` |
| 10 | 11 | 99 | 1.78 | `0x000000000037459e` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 10 | 12 | 99 | 1.66 | `0x000000000037411f` | `<aho_corasick::packed::teddy::generic::Teddy<_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 10 | 13 | 99 | 1.64 | `0x0000000000178810` | `grep_searcher::sink::SinkError::error_config` | `symbol-table` |
| 10 | 14 | 99 | 1.61 | `0x0000000000375d48` | `memchr::arch::x86_64::avx2::memchr::Two::find_raw` | `symbol-table` |
| 10 | 15 | 99 | 1.60 | `0x000000000018b0a1` | `encoding_rs_io::DecodeReaderBytes<R,B>::fill` | `symbol-table` |
| 10 | 16 | 99 | 1.59 | `0x0000000000178623` | `grep_searcher::line_buffer::LineBuffer::fill` | `symbol-table` |
| 10 | 17 | 99 | 1.57 | `0x00000000003748a5` | `<aho_corasick::util::prefilter::Memmem as aho_corasick::util::prefilter::PrefilterI>::find_in` | `symbol-table` |
| 10 | 18 | 99 | 1.54 | `0x0000000000374663` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 10 | 19 | 99 | 1.52 | `0x0000000000178070` | `grep_searcher::line_buffer::LineBuffer::fill` | `symbol-table` |
| 10 | 20 | 99 | 1.48 | `0x00000000001789b2` | `grep_searcher::searcher::core::Core<M,S>::detect_binary` | `symbol-table` |
| 10 | 21 | 99 | 1.48 | `0x00000000003772d0` | `memchr::arch::x86_64::memchr::memrchr3_raw::find_avx2` | `symbol-table` |
| 10 | 22 | 99 | 1.45 | `0x0000000000178967` | `grep_searcher::searcher::core::Core<M,S>::detect_binary` | `symbol-table` |
| 10 | 23 | 99 | 1.44 | `0x000000000018aff8` | `encoding_rs_io::DecodeReaderBytes<R,B>::fill` | `symbol-table` |
| 10 | 24 | 99 | 1.42 | `0x0000000000178997` | `grep_searcher::searcher::core::Core<M,S>::detect_binary` | `symbol-table` |
| 10 | 25 | 99 | 1.41 | `0x000000000037413d` | `<aho_corasick::packed::teddy::generic::Teddy<_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 10 | 26 | 99 | 1.40 | `0x0000000000374123` | `<aho_corasick::packed::teddy::generic::Teddy<_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 10 | 27 | 99 | 1.39 | `0x000000000017892a` | `grep_searcher::searcher::core::Core<M,S>::count_lines` | `symbol-table` |
| 10 | 28 | 99 | 1.32 | `0x00000000003744bc` | `<aho_corasick::nfa::noncontiguous::NFA as aho_corasick::automaton::Automaton>::match_pattern` | `symbol-table` |
| 10 | 29 | 99 | 1.32 | `0x0000000000178983` | `grep_searcher::searcher::core::Core<M,S>::detect_binary` | `symbol-table` |
| 10 | 30 | 99 | 1.26 | `0x0000000000178989` | `grep_searcher::searcher::core::Core<M,S>::detect_binary` | `symbol-table` |
| 01 | 1 | 98 | 4.34 | `0x0000000000374603` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/aho-corasick-1.1.3/src/packed/teddy/generic.rs:53` |
| 01 | 2 | 98 | 3.17 | `0x0000000000178815` | `grep_searcher::sink::SinkError::error_config` | `symbol-table` |
| 01 | 3 | 98 | 2.78 | `0x000000000018b09e` | `encoding_rs_io::DecodeReaderBytes<R,B>::fill` | `symbol-table` |
| 01 | 4 | 98 | 2.66 | `0x000000000037416b` | `<aho_corasick::packed::teddy::generic::Teddy<_> as core::fmt::Debug>::fmt` | `<aho_corasick::packed::teddy::generic::Teddy<_> as core::fmt::Debug>::fmt at aho_corasick.767c51d147f47206-cgu.0:?` |
| 01 | 5 | 98 | 2.23 | `0x000000000037495a` | `<aho_corasick::util::prefilter::Packed as aho_corasick::util::prefilter::PrefilterI>::find_in` | `<aho_corasick::util::prefilter::Packed as aho_corasick::util::prefilter::PrefilterI>::find_in at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/aho-corasick-1.1.3/src/util/prefilter.rs:333` |
| 01 | 6 | 98 | 2.22 | `0x000000000037467e` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/aho-corasick-1.1.3/src/packed/teddy/generic.rs:53` |
| 01 | 7 | 98 | 2.16 | `0x00000000001789a8` | `grep_searcher::searcher::core::Core<M,S>::detect_binary` | `symbol-table` |
| 01 | 8 | 98 | 2.15 | `0x00000000003744a3` | `core::option::Option<T>::unwrap` | `core::option::Option<T>::unwrap at /rustc/54a8a1db604e4caff93e26e167ad4a6fde9f0681/library/core/src/option.rs:1010 |  (inlined by) <aho_corasick::nfa::noncontiguous::NFA as aho_corasick::automaton::Automaton>::match_pattern at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/aho-corasick-1.1.3/src/nfa/noncontiguous.rs:685` |
| 01 | 9 | 98 | 1.96 | `0x00000000003748ad` | `<aho_corasick::util::prefilter::Memmem as aho_corasick::util::prefilter::PrefilterI>::find_in` | `symbol-table` |
| 01 | 10 | 98 | 1.94 | `0x000000000037459e` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 01 | 11 | 98 | 1.83 | `0x000000000029c5df` | `<&A as regex_automata::dfa::automaton::Automaton>::next_eoi_state` | `symbol-table` |
| 01 | 12 | 98 | 1.82 | `0x00000000003745cf` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 01 | 13 | 98 | 1.74 | `0x000000000018aff9` | `encoding_rs_io::DecodeReaderBytes<R,B>::fill` | `symbol-table` |
| 01 | 14 | 98 | 1.73 | `0x000000000018afff` | `encoding_rs_io::DecodeReaderBytes<R,B>::fill` | `symbol-table` |
| 01 | 15 | 98 | 1.57 | `0x0000000000373f3a` | `<aho_corasick::nfa::contiguous::NFA as aho_corasick::automaton::Automaton>::match_pattern` | `symbol-table` |
| 01 | 16 | 98 | 1.50 | `0x0000000000375578` | `memchr::arch::x86_64::avx2::packedpair::Finder::find_impl` | `symbol-table` |
| 01 | 17 | 98 | 1.49 | `0x00000000003746c8` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 01 | 18 | 98 | 1.47 | `0x00000000001787ff` | `grep_searcher::sink::SinkError::error_config` | `symbol-table` |
| 01 | 19 | 98 | 1.46 | `0x000000000037466a` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 01 | 20 | 98 | 1.43 | `0x0000000000204650` | `<&mut S as grep_searcher::sink::Sink>::finish` | `symbol-table` |
| 01 | 21 | 98 | 1.43 | `0x0000000000374112` | `<aho_corasick::packed::teddy::generic::Teddy<_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 01 | 22 | 98 | 1.42 | `0x000000000037411f` | `<aho_corasick::packed::teddy::generic::Teddy<_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 01 | 23 | 98 | 1.40 | `0x00000000001779ba` | `grep_printer::standard::StandardSink<M,W>::record_matches` | `symbol-table` |
| 01 | 24 | 98 | 1.37 | `0x00000000003772d1` | `memchr::arch::x86_64::memchr::memrchr3_raw::find_avx2` | `symbol-table` |
| 01 | 25 | 98 | 1.37 | `0x000000000029c598` | `<&A as regex_automata::dfa::automaton::Automaton>::match_pattern` | `symbol-table` |
| 01 | 26 | 98 | 1.36 | `0x000000000018af98` | `encoding_rs_io::DecodeReaderBytes<R,B>::fill` | `symbol-table` |
| 01 | 27 | 98 | 1.30 | `0x000000000029c5af` | `<&A as regex_automata::dfa::automaton::Automaton>::match_pattern` | `symbol-table` |
| 01 | 28 | 98 | 1.30 | `0x000000000029c5cf` | `<&A as regex_automata::dfa::automaton::Automaton>::match_pattern` | `symbol-table` |
| 01 | 29 | 98 | 1.28 | `0x000000000017797d` | `grep_printer::standard::StandardSink<M,W>::record_matches` | `symbol-table` |
| 01 | 30 | 98 | 1.26 | `0x0000000000178989` | `grep_searcher::searcher::core::Core<M,S>::detect_binary` | `symbol-table` |
| 11 | 1 | 97 | 6.50 | `0x000000000037459e` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/aho-corasick-1.1.3/src/packed/teddy/generic.rs:56` |
| 11 | 2 | 97 | 3.19 | `0x00000000003745f9` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/aho-corasick-1.1.3/src/packed/teddy/generic.rs:59` |
| 11 | 3 | 97 | 2.59 | `0x00000000003745fe` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/aho-corasick-1.1.3/src/packed/teddy/generic.rs:56` |
| 11 | 4 | 97 | 2.57 | `0x00000000001787c7` | `grep_searcher::line_buffer::LineBuffer::fill` | `symbol-table` |
| 11 | 5 | 97 | 2.39 | `0x00000000001787a0` | `grep_searcher::line_buffer::LineBuffer::fill` | `symbol-table` |
| 11 | 6 | 97 | 2.31 | `0x000000000018b09e` | `encoding_rs_io::DecodeReaderBytes<R,B>::fill` | `symbol-table` |
| 11 | 7 | 97 | 2.23 | `0x00000000003745f5` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/aho-corasick-1.1.3/src/packed/teddy/generic.rs:53` |
| 11 | 8 | 97 | 2.20 | `0x00000000003772f3` | `memchr::arch::x86_64::avx2::memchr::Three::new_unchecked` | `memchr::arch::x86_64::avx2::memchr::Three::new_unchecked at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/memchr-2.7.6/src/arch/x86_64/avx2/memchr.rs:940 |  (inlined by) memchr::arch::x86_64::memchr::memrchr3_raw::find_avx2 at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/memchr-2.7.6/src/arch/x86_64/memchr.rs:84` |
| 11 | 9 | 97 | 1.95 | `0x000000000018afa8` | `encoding_rs_io::DecodeReaderBytes<R,B>::fill` | `symbol-table` |
| 11 | 10 | 97 | 1.70 | `0x0000000000373e87` | `<aho_corasick::nfa::contiguous::NFA as aho_corasick::automaton::Automaton>::next_state` | `symbol-table` |
| 11 | 11 | 97 | 1.68 | `0x0000000000178899` | `grep_searcher::sink::SinkError::error_config` | `symbol-table` |
| 11 | 12 | 97 | 1.65 | `0x000000000018afff` | `encoding_rs_io::DecodeReaderBytes<R,B>::fill` | `symbol-table` |
| 11 | 13 | 97 | 1.64 | `0x000000000017807e` | `grep_searcher::line_buffer::LineBuffer::fill` | `symbol-table` |
| 11 | 14 | 97 | 1.56 | `0x0000000000374607` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 11 | 15 | 97 | 1.53 | `0x000000000029c5df` | `<&A as regex_automata::dfa::automaton::Automaton>::next_eoi_state` | `symbol-table` |
| 11 | 16 | 97 | 1.53 | `0x000000000017850d` | `grep_searcher::line_buffer::LineBuffer::fill` | `symbol-table` |
| 11 | 17 | 97 | 1.51 | `0x0000000000375d6d` | `memchr::arch::x86_64::avx2::memchr::Two::find_raw` | `symbol-table` |
| 11 | 18 | 97 | 1.51 | `0x0000000000177962` | `grep_printer::standard::StandardSink<M,W>::record_matches` | `symbol-table` |
| 11 | 19 | 97 | 1.48 | `0x00000000003745cf` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 11 | 20 | 97 | 1.43 | `0x00000000001779cf` | `grep_printer::standard::StandardSink<M,W>::record_matches` | `symbol-table` |
| 11 | 21 | 97 | 1.42 | `0x000000000037470d` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 11 | 22 | 97 | 1.40 | `0x000000000037416b` | `<aho_corasick::packed::teddy::generic::Teddy<_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 11 | 23 | 97 | 1.39 | `0x0000000000178655` | `grep_searcher::line_buffer::LineBuffer::fill` | `symbol-table` |
| 11 | 24 | 97 | 1.32 | `0x0000000000374677` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 11 | 25 | 97 | 1.30 | `0x0000000000177b48` | `grep_printer::hyperlink::Interpolator::begin` | `symbol-table` |
| 11 | 26 | 97 | 1.29 | `0x00000000003745dd` | `<aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt` | `symbol-table` |
| 11 | 27 | 97 | 1.27 | `0x000000000029c526` | `<&A as regex_automata::dfa::automaton::Automaton>::match_pattern` | `symbol-table` |
| 11 | 28 | 97 | 1.24 | `0x000000000020465e` | `<&mut S as grep_searcher::sink::Sink>::finish` | `symbol-table` |
| 11 | 29 | 97 | 1.24 | `0x00000000001779d1` | `grep_printer::standard::StandardSink<M,W>::record_matches` | `symbol-table` |
| 11 | 30 | 97 | 1.23 | `0x0000000000374109` | `<aho_corasick::packed::teddy::generic::Teddy<_> as core::fmt::Debug>::fmt` | `symbol-table` |

## bat

| Cell | Rank | Samples | Self % | Address | Function | Location |
|---|---:|---:|---:|---|---|---|
| 00 | 1 | 1K | 1.43 | `0x000000000053af5f` | `address only` | `unresolved` |
| 00 | 2 | 1K | 1.21 | `0x000000000061bd02` | `address only` | `unresolved` |
| 00 | 3 | 1K | 1.15 | `0x0000000000532826` | `address only` | `unresolved` |
| 00 | 4 | 1K | 1.11 | `0x000000000053af7a` | `address only` | `unresolved` |
| 00 | 5 | 1K | 1.10 | `0x000000000053af50` | `address only` | `unresolved` |
| 00 | 6 | 1K | 0.95 | `0x000000000061c036` | `address only` | `unresolved` |
| 00 | 7 | 1K | 0.94 | `0x000000000061c013` | `address only` | `unresolved` |
| 00 | 8 | 1K | 0.84 | `0x000000000034cc10` | `address only` | `unresolved` |
| 00 | 9 | 1K | 0.76 | `0x000000000034cbb2` | `address only` | `unresolved` |
| 00 | 10 | 1K | 0.74 | `0x000000000053ab97` | `address only` | `unresolved` |
| 00 | 11 | 1K | 0.74 | `0x000000000053af3f` | `address only` | `unresolved` |
| 00 | 12 | 1K | 0.74 | `0x000000000053af88` | `address only` | `unresolved` |
| 00 | 13 | 1K | 0.73 | `0x0000000000645a11` | `address only` | `unresolved` |
| 00 | 14 | 1K | 0.66 | `0x000000000053af30` | `address only` | `unresolved` |
| 00 | 15 | 1K | 0.65 | `0x000000000053af03` | `address only` | `unresolved` |
| 00 | 16 | 1K | 0.64 | `0x000000000053af3a` | `address only` | `unresolved` |
| 00 | 17 | 1K | 0.57 | `0x000000000034ca67` | `address only` | `unresolved` |
| 00 | 18 | 1K | 0.57 | `0x0000000000622dc8` | `address only` | `unresolved` |
| 00 | 19 | 1K | 0.57 | `0x0000000000645a00` | `address only` | `unresolved` |
| 00 | 20 | 1K | 0.56 | `0x000000000053af08` | `address only` | `unresolved` |
| 00 | 21 | 1K | 0.55 | `0x000000000061bcb3` | `address only` | `unresolved` |
| 00 | 22 | 1K | 0.54 | `0x000000000053af67` | `address only` | `unresolved` |
| 10 | 1 | 1K | 1.37 | `0x000000000034cc10` | `address only` | `unresolved` |
| 10 | 2 | 1K | 1.35 | `0x0000000000532826` | `address only` | `unresolved` |
| 10 | 3 | 1K | 1.25 | `0x000000000053af5f` | `address only` | `unresolved` |
| 10 | 4 | 1K | 1.16 | `0x000000000053aefb` | `address only` | `unresolved` |
| 10 | 5 | 1K | 1.08 | `0x000000000053af67` | `address only` | `unresolved` |
| 10 | 6 | 1K | 0.97 | `0x000000000053aee2` | `address only` | `unresolved` |
| 10 | 7 | 1K | 0.96 | `0x000000000034cbb2` | `address only` | `unresolved` |
| 10 | 8 | 1K | 0.96 | `0x0000000000645a00` | `address only` | `unresolved` |
| 10 | 9 | 1K | 0.87 | `0x000000000053af88` | `address only` | `unresolved` |
| 10 | 10 | 1K | 0.86 | `0x000000000053af3d` | `address only` | `unresolved` |
| 10 | 11 | 1K | 0.86 | `0x000000000053af03` | `address only` | `unresolved` |
| 10 | 12 | 1K | 0.86 | `0x000000000061bd02` | `address only` | `unresolved` |
| 10 | 13 | 1K | 0.77 | `0x000000000053aef8` | `address only` | `unresolved` |
| 10 | 14 | 1K | 0.69 | `0x000000000061c036` | `address only` | `unresolved` |
| 10 | 15 | 1K | 0.68 | `0x000000000053af30` | `address only` | `unresolved` |
| 10 | 16 | 1K | 0.61 | `0x0000000000532815` | `address only` | `unresolved` |
| 10 | 17 | 1K | 0.59 | `0x000000000053af7a` | `address only` | `unresolved` |
| 10 | 18 | 1K | 0.59 | `0x000000000053ae69` | `address only` | `unresolved` |
| 10 | 19 | 1K | 0.58 | `0x000000000061bcfd` | `address only` | `unresolved` |
| 10 | 20 | 1K | 0.58 | `0x000000000053ab97` | `address only` | `unresolved` |
| 10 | 21 | 1K | 0.58 | `0x00000000005327f8` | `address only` | `unresolved` |
| 10 | 22 | 1K | 0.57 | `0x000000000053af3f` | `address only` | `unresolved` |
| 10 | 23 | 1K | 0.56 | `0x000000000053af50` | `address only` | `unresolved` |
| 01 | 1 | 1K | 1.44 | `0x000000000053af7a` | `address only` | `unresolved` |
| 01 | 2 | 1K | 1.26 | `0x000000000034cc10` | `address only` | `unresolved` |
| 01 | 3 | 1K | 1.17 | `0x000000000053aee2` | `address only` | `unresolved` |
| 01 | 4 | 1K | 1.15 | `0x000000000061bd02` | `address only` | `unresolved` |
| 01 | 5 | 1K | 1.07 | `0x000000000053af5f` | `address only` | `unresolved` |
| 01 | 6 | 1K | 0.99 | `0x000000000061c036` | `address only` | `unresolved` |
| 01 | 7 | 1K | 0.98 | `0x000000000053af67` | `address only` | `unresolved` |
| 01 | 8 | 1K | 0.77 | `0x0000000000532815` | `address only` | `unresolved` |
| 01 | 9 | 1K | 0.77 | `0x0000000000645a11` | `address only` | `unresolved` |
| 01 | 10 | 1K | 0.76 | `0x000000000061c013` | `address only` | `unresolved` |
| 01 | 11 | 1K | 0.68 | `0x000000000053af3f` | `address only` | `unresolved` |
| 01 | 12 | 1K | 0.67 | `0x000000000053ab54` | `address only` | `unresolved` |
| 01 | 13 | 1K | 0.67 | `0x000000000061bcfd` | `address only` | `unresolved` |
| 01 | 14 | 1K | 0.67 | `0x000000000053af3a` | `address only` | `unresolved` |
| 01 | 15 | 1K | 0.59 | `0x000000000053ab97` | `address only` | `unresolved` |
| 01 | 16 | 1K | 0.58 | `0x000000000053ab64` | `address only` | `unresolved` |
| 01 | 17 | 1K | 0.58 | `0x000000000053ab35` | `address only` | `unresolved` |
| 01 | 18 | 1K | 0.58 | `0x000000000053af03` | `address only` | `unresolved` |
| 01 | 19 | 1K | 0.57 | `0x000000000053ab8a` | `address only` | `unresolved` |
| 01 | 20 | 1K | 0.57 | `0x000000000053ab8f` | `address only` | `unresolved` |
| 01 | 21 | 1K | 0.56 | `0x000000000053af30` | `address only` | `unresolved` |
| 01 | 22 | 1K | 0.51 | `0x000000000053abbf` | `address only` | `unresolved` |
| 01 | 23 | 1K | 0.50 | `0x000000000034cbc4` | `address only` | `unresolved` |
| 11 | 1 | 1K | 1.09 | `0x000000000061c036` | `address only` | `unresolved` |
| 11 | 2 | 1K | 1.00 | `0x000000000053af5f` | `address only` | `unresolved` |
| 11 | 3 | 1K | 0.90 | `0x0000000000532826` | `address only` | `unresolved` |
| 11 | 4 | 1K | 0.89 | `0x000000000053af50` | `address only` | `unresolved` |
| 11 | 5 | 1K | 0.81 | `0x000000000053af67` | `address only` | `unresolved` |
| 11 | 6 | 1K | 0.80 | `0x000000000053ab4e` | `address only` | `unresolved` |
| 11 | 7 | 1K | 0.80 | `0x0000000000645a11` | `address only` | `unresolved` |
| 11 | 8 | 1K | 0.79 | `0x000000000053af3a` | `address only` | `unresolved` |
| 11 | 9 | 1K | 0.78 | `0x000000000053ab8d` | `address only` | `unresolved` |
| 11 | 10 | 1K | 0.78 | `0x000000000053ab97` | `address only` | `unresolved` |
| 11 | 11 | 1K | 0.78 | `0x000000000061bd02` | `address only` | `unresolved` |
| 11 | 12 | 1K | 0.70 | `0x000000000053aefb` | `address only` | `unresolved` |
| 11 | 13 | 1K | 0.69 | `0x000000000034cc10` | `address only` | `unresolved` |
| 11 | 14 | 1K | 0.69 | `0x000000000053aee2` | `address only` | `unresolved` |
| 11 | 15 | 1K | 0.68 | `0x000000000061c013` | `address only` | `unresolved` |
| 11 | 16 | 1K | 0.60 | `0x000000000053ab8a` | `address only` | `unresolved` |
| 11 | 17 | 1K | 0.59 | `0x000000000053ab60` | `address only` | `unresolved` |
| 11 | 18 | 1K | 0.59 | `0x000000000053af3d` | `address only` | `unresolved` |
| 11 | 19 | 1K | 0.58 | `0x000000000053af7a` | `address only` | `unresolved` |

## quinn

| Cell | Rank | Samples | Self % | Address | Function | Location |
|---|---:|---:|---:|---|---|---|
| 00 | 1 | 14 | 12.03 | `0x000000000042f44f` | `ring_core_0_17_14__gcm_init_vpclmulqdq_avx2` | `ring_core_0_17_14__gcm_init_vpclmulqdq_avx2 at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/ring-0.17.14/pregenerated/aes-gcm-avx2-x86_64-elf.S:89` |
| 00 | 2 | 14 | 11.66 | `0x0000000000400efd` | `ring::rsa::padding::mgf1` | `ring::rsa::padding::mgf1 at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/ring-0.17.14/src/rsa/padding.rs:75` |
| 00 | 3 | 14 | 10.90 | `0x00000000002e4697` | `quinn_proto::connection::Connection::handle_event` | `symbol-table` |
| 00 | 4 | 14 | 10.84 | `0x000000000043196b` | `ring_core_0_17_14__aes_hw_ctr32_encrypt_blocks` | `ring_core_0_17_14__aes_hw_ctr32_encrypt_blocks at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/ring-0.17.14/pregenerated/aesni-x86_64-elf.S:623` |
| 00 | 5 | 14 | 7.90 | `0x000000000042f6ac` | `ring_core_0_17_14__aes_gcm_enc_update_vaes_avx2` | `ring_core_0_17_14__aes_gcm_enc_update_vaes_avx2 at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/ring-0.17.14/pregenerated/aes-gcm-avx2-x86_64-elf.S:291` |
| 00 | 6 | 14 | 7.10 | `0x000000000042f3c6` | `ring_core_0_17_14__gcm_init_vpclmulqdq_avx2` | `ring_core_0_17_14__gcm_init_vpclmulqdq_avx2 at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/ring-0.17.14/pregenerated/aes-gcm-avx2-x86_64-elf.S:51` |
| 00 | 7 | 14 | 3.95 | `0x000000000042f51a` | `ring_core_0_17_14__gcm_init_vpclmulqdq_avx2` | `ring_core_0_17_14__gcm_init_vpclmulqdq_avx2 at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/ring-0.17.14/pregenerated/aes-gcm-avx2-x86_64-elf.S:139` |
| 00 | 8 | 14 | 2.67 | `0x000000000035cb78` | `alloc::raw_vec::RawVecInner<A>::try_allocate_in` | `alloc::raw_vec::RawVecInner<A>::try_allocate_in at /rustc/54a8a1db604e4caff93e26e167ad4a6fde9f0681/library/alloc/src/raw_vec/mod.rs:475 |  (inlined by) alloc::raw_vec::RawVecInner<A>::with_capacity_in at /rustc/54a8a1db604e4caff93e26e167ad4a6fde9f0681/library/alloc/src/raw_vec/mod.rs:430 |  (inlined by) alloc::raw_vec::RawVec<T,A>::with_capacity_in at /rustc/54a8a1db604e4caff93e26e167ad4a6fde9f0681/library/alloc/src/raw_vec/mod.rs:192 |  (inlined by) alloc::vec::Vec<T,A>::with_capacity_in at /rustc/54a8a1db604e4caff93e26e167ad4a6fde9f0681/library/alloc/src/vec/mod.rs:931 |  (inlined by) <T as alloc::slice::<impl [T]>::to_vec_in::ConvertVec>::to_vec at /rustc/54a8a1db604e4caff93e26e167ad4a6fde9f0681/library/alloc/src/slice.rs:445 |  (inlined by) alloc::slice::<impl [T]>::to_vec_in at /rustc/54a8a1db604e4caff93e26e167ad4a6fde9f0681/library/alloc/src/slice.rs:398 |  (inlined by) alloc::slice::<impl [T]>::to_vec at /rustc/54a8a1db604e4caff93e26e167ad4a6fde9f0681/library/alloc/src/slice.rs:374 |  (inlined by) bytes::bytes::shared_to_vec_impl at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/bytes-1.11.1/src/bytes.rs:1402` |
| 00 | 9 | 14 | 2.44 | `0x00000000002eb5f4` | `quinn_proto::connection::Connection::poll_transmit` | `symbol-table` |
| 00 | 10 | 14 | 2.44 | `0x00000000004303a9` | `_aesni_ctr32_ghash_6x` | `symbol-table` |
| 00 | 11 | 14 | 2.14 | `0x0000000000315f3d` | `quinn_proto::connection::Connection::kill` | `symbol-table` |
| 10 | 1 | 17 | 9.71 | `0x000000000042f392` | `ring_core_0_17_14__ChaCha20_ctr32_avx2` | `ring_core_0_17_14__ChaCha20_ctr32_avx2 at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/ring-0.17.14/pregenerated/chacha-x86_64-elf.S:1459` |
| 10 | 2 | 17 | 9.34 | `0x00000000002eb541` | `quinn_proto::connection::Connection::poll_transmit` | `symbol-table` |
| 10 | 3 | 17 | 8.93 | `0x000000000042fa80` | `ring_core_0_17_14__aes_gcm_enc_update_vaes_avx2` | `ring_core_0_17_14__aes_gcm_enc_update_vaes_avx2 at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/ring-0.17.14/pregenerated/aes-gcm-avx2-x86_64-elf.S:539` |
| 10 | 4 | 17 | 8.35 | `0x00000000002e5273` | `quinn_proto::connection::Connection::write_crypto` | `symbol-table` |
| 10 | 5 | 17 | 8.33 | `0x00000000003163cb` | `quinn_proto::connection::Connection::init_0rtt` | `symbol-table` |
| 10 | 6 | 17 | 8.08 | `0x0000000000326a1a` | `quinn_proto::packet::PartialDecode::new` | `symbol-table` |
| 10 | 7 | 17 | 6.56 | `0x000000000036b390` | `tokio::runtime::task::core::Trailer::wake_join` | `symbol-table` |
| 10 | 8 | 17 | 6.28 | `0x00000000003431d8` | `<rustls::error::Error as core::clone::Clone>::clone` | `symbol-table` |
| 10 | 9 | 17 | 3.74 | `0x00000000002d2885` | `quinn::endpoint::Endpoint::client` | `symbol-table` |
| 10 | 10 | 17 | 3.15 | `0x000000000034908e` | `alloc::collections::btree::node::BalancingContext<K,V>::do_merge` | `symbol-table` |
| 10 | 11 | 17 | 1.93 | `0x00000000002d2f44` | `quinn::endpoint::Endpoint::server` | `symbol-table` |
| 10 | 12 | 17 | 1.93 | `0x000000000030fa44` | `quinn_proto::connection::Connection::process_early_payload` | `symbol-table` |
| 10 | 13 | 17 | 1.57 | `0x000000000042fd22` | `ring_core_0_17_14__aes_gcm_enc_update_vaes_avx2` | `symbol-table` |
| 01 | 1 | 14 | 12.24 | `0x000000000043196b` | `ring_core_0_17_14__aes_hw_ctr32_encrypt_blocks` | `symbol-table` |
| 01 | 2 | 14 | 11.89 | `0x00000000002d35a3` | `quinn::endpoint::RecvState::poll_socket` | `symbol-table` |
| 01 | 3 | 14 | 11.06 | `0x0000000000342aa8` | `<rustls::error::Error as core::clone::Clone>::clone` | `symbol-table` |
| 01 | 4 | 14 | 9.57 | `0x00000000003670d9` | `tokio::sync::oneshot::State::set_complete` | `tokio::sync::oneshot::State::set_complete at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/tokio-1.52.0/src/sync/oneshot.rs:1538 |  (inlined by) tokio::sync::oneshot::Inner<T>::complete at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/tokio-1.52.0/src/sync/oneshot.rs:1299 |  (inlined by) <tokio::sync::oneshot::Sender<T> as core::ops::drop::Drop>::drop at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/tokio-1.52.0/src/sync/oneshot.rs:874 |  (inlined by) core::ptr::drop_in_place<tokio::sync::oneshot::Sender<()>> at /rustc/54a8a1db604e4caff93e26e167ad4a6fde9f0681/library/core/src/ptr/mod.rs:804 |  (inlined by) alloc::sync::Arc<T,A>::drop_slow at /rustc/54a8a1db604e4caff93e26e167ad4a6fde9f0681/library/alloc/src/sync.rs:1923` |
| 01 | 5 | 14 | 7.30 | `0x00000000002fd1f4` | `quinn_proto::connection::Connection::populate_packet` | `symbol-table` |
| 01 | 6 | 14 | 6.75 | `0x00000000003ccada` | `<rustls::enums::CipherSuite as core::convert::From<u16>>::from` | `symbol-table` |
| 01 | 7 | 14 | 4.75 | `0x0000000000431fec` | `ring_core_0_17_14__gcm_init_clmul` | `ring_core_0_17_14__gcm_init_clmul at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/ring-0.17.14/pregenerated/ghash-x86_64-elf.S:77` |
| 01 | 8 | 14 | 2.55 | `0x00000000002d29f2` | `quinn::endpoint::Endpoint::client` | `quinn::endpoint::Endpoint::client at /mnt/d/MIR_LLVM_NEW/quinn/quinn/src/endpoint.rs:?` |
| 01 | 9 | 14 | 2.47 | `0x00000000002e5273` | `quinn_proto::connection::Connection::write_crypto` | `symbol-table` |
| 01 | 10 | 14 | 2.47 | `0x000000000042f47f` | `ring_core_0_17_14__gcm_init_vpclmulqdq_avx2` | `symbol-table` |
| 01 | 11 | 14 | 2.47 | `0x000000000042f663` | `ring_core_0_17_14__aes_gcm_enc_update_vaes_avx2` | `symbol-table` |
| 11 | 1 | 15 | 13.65 | `0x000000000030fbb3` | `quinn_proto::connection::Connection::process_early_payload` | `symbol-table` |
| 11 | 2 | 15 | 12.94 | `0x0000000000355d5b` | `<quinn_proto::bloom_token_log::BloomTokenLog as quinn_proto::token::TokenLog>::check_and_insert` | `symbol-table` |
| 11 | 3 | 15 | 12.08 | `0x0000000000375530` | `<rustls::msgs::handshake::CertificateRequestExtensions as rustls::msgs::codec::Codec>::encode` | `symbol-table` |
| 11 | 4 | 15 | 11.08 | `0x00000000002fcced` | `quinn_proto::connection::Connection::populate_packet` | `symbol-table` |
| 11 | 5 | 15 | 10.64 | `0x000000000034d8a4` | `<quinn_proto::frame::FrameType as core::fmt::Display>::fmt` | `symbol-table` |
| 11 | 6 | 15 | 8.40 | `0x000000000034d9e9` | `<core::alloc::layout::LayoutError as core::fmt::Debug>::fmt` | `<core::alloc::layout::LayoutError as core::fmt::Debug>::fmt at quinn_proto.7e5c669909530882-cgu.0:?` |
| 11 | 7 | 15 | 7.59 | `0x000000000042f570` | `ring_core_0_17_14__gcm_ghash_vpclmulqdq_avx2_1` | `ring_core_0_17_14__gcm_ghash_vpclmulqdq_avx2_1 at /home/fjx/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/ring-0.17.14/pregenerated/aes-gcm-avx2-x86_64-elf.S:184` |
| 11 | 8 | 15 | 2.51 | `0x00000000003437e6` | `<rustls::error::Error as core::clone::Clone>::clone` | `symbol-table` |
| 11 | 9 | 15 | 2.51 | `0x00000000003438b1` | `<rustls::error::Error as core::clone::Clone>::clone` | `symbol-table` |
| 11 | 10 | 15 | 2.51 | `0x000000000042f7c5` | `ring_core_0_17_14__aes_gcm_enc_update_vaes_avx2` | `symbol-table` |
| 11 | 11 | 15 | 2.45 | `0x0000000000330c40` | `quinn_proto::endpoint::Endpoint::accept` | `symbol-table` |
| 11 | 12 | 15 | 2.45 | `0x000000000035cc4e` | `bytes::bytes::promotable_odd_drop` | `symbol-table` |
| 11 | 13 | 15 | 2.32 | `0x00000000002f4a47` | `quinn_proto::connection::Connection::on_ack_received` | `symbol-table` |
