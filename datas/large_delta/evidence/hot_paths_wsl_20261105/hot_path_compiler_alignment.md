# Dynamic hot-path evidence for the three selected real-world cases

The profiles were collected in WSL2 with `perf record -F 49 -g --call-graph dwarf` on the four captured binaries.
The event is sampled user-space CPU cycles.  A profile identifies code that was sampled during the supplied smoke command; it does not establish that a function caused the historical interaction or that it is the only hot path.

## ripgrep: `ForceInline` × `-disable-cleanups`

Historical frozen estimate: Δ=+0.5125; cell medians (00,10,01,11): 9.715 / 11.976 / 12.565 / 9.674 s.

| Cell | perf samples | Top sampled functions or addresses |
|---|---:|---|
| 00 | 121 | encoding_rs_io::DecodeReaderBytes<R,B>::fill (4.62%); memchr::arch::generic::packedpair::Finder<V>::find (3.04%); <aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt (3.04%); <aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt (2.39%); aho_corasick::nfa::contiguous::State::kind (2.27%) |
| 10 | 99 | <aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt (4.13%); <aho_corasick::packed::teddy::generic::Teddy<_> as core::fmt::Debug>::fmt (3.56%); grep_searcher::line_buffer::LineBuffer::fill (2.68%); <aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt (2.54%); <aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt (2.33%) |
| 01 | 98 | <aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt (4.34%); grep_searcher::sink::SinkError::error_config (3.17%); encoding_rs_io::DecodeReaderBytes<R,B>::fill (2.78%); <aho_corasick::packed::teddy::generic::Teddy<_> as core::fmt::Debug>::fmt (2.66%); <aho_corasick::util::prefilter::Packed as aho_corasick::util::prefilter::PrefilterI>::find_in (2.23%) |
| 11 | 97 | <aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt (6.50%); <aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt (3.19%); <aho_corasick::packed::teddy::generic::Slim<V,_> as core::fmt::Debug>::fmt (2.59%); grep_searcher::line_buffer::LineBuffer::fill (2.57%); grep_searcher::line_buffer::LineBuffer::fill (2.39%) |

Build IDs for the profiled executable:
00=fddca4790d4dfeed9a4a0632fb010a8c3547d56a; 10=fddca4790d4dfeed9a4a0632fb010a8c3547d56a; 01=fddca4790d4dfeed9a4a0632fb010a8c3547d56a; 11=fddca4790d4dfeed9a4a0632fb010a8c3547d56a

The symbolized samples repeatedly include Aho--Corasick Teddy routines, `memchr` packed-pair search, the grep line buffer, and encoding input code. These are plausible portions of the supplied search command's execution path. The four profiled executables share the same build ID, and the static four-cell comparison reports no shared LLVM-IR or assembly module changes; therefore the profile does not provide evidence of a cell-specific ForceInline/cleanup code-generation change.

## bat: `ImpossiblePredicates` × `-disable-vp`

Historical frozen estimate: Δ=-0.4237; cell medians (00,10,01,11): 23.183 / 23.285 / 23.219 / 36.365 s.

| Cell | perf samples | Top sampled functions or addresses |
|---|---:|---|
| 00 | 1K | 0x000000000053af5f (1.43%); 0x000000000061bd02 (1.21%); 0x0000000000532826 (1.15%); 0x000000000053af7a (1.11%); 0x000000000053af50 (1.10%) |
| 10 | 1K | 0x000000000034cc10 (1.37%); 0x0000000000532826 (1.35%); 0x000000000053af5f (1.25%); 0x000000000053aefb (1.16%); 0x000000000053af67 (1.08%) |
| 01 | 1K | 0x000000000053af7a (1.44%); 0x000000000034cc10 (1.26%); 0x000000000053aee2 (1.17%); 0x000000000061bd02 (1.15%); 0x000000000053af5f (1.07%) |
| 11 | 1K | 0x000000000061c036 (1.09%); 0x000000000053af5f (1.00%); 0x0000000000532826 (0.90%); 0x000000000053af50 (0.89%); 0x000000000053af67 (0.81%) |

Build IDs for the profiled executable:
00=8045414c4c6f45d1462c74483626e25284430ea9; 10=8045414c4c6f45d1462c74483626e25284430ea9; 01=d3608aa96fc7267b4747dd57d83f2cce1fd0fd5c; 11=d3608aa96fc7267b4747dd57d83f2cce1fd0fd5c

The binary is stripped, so the profile remains address-level. The four cells have about 1K samples each, making this the strongest dynamic capture of the three cases, but the addresses cannot be mapped to functions without a matching unstripped/DWARF binary. Static artifacts show LLVM-IR and assembly module changes in 21/165, 19/165, and 18/165 modules for cells 10, 01, and 11 versus 00, respectively; the dynamic profile alone cannot show that those changed modules are on the measured path.

## quinn: `DataflowConstProp` × `-disable-tail-calls`

Historical frozen estimate: Δ=+0.3770; cell medians (00,10,01,11): 5.543 / 6.813 / 5.916 / 5.465 s.

| Cell | perf samples | Top sampled functions or addresses |
|---|---:|---|
| 00 | 14 | ring_core_0_17_14__gcm_init_vpclmulqdq_avx2 (12.03%); ring::rsa::padding::mgf1 (11.66%); quinn_proto::connection::Connection::handle_event (10.90%); ring_core_0_17_14__aes_hw_ctr32_encrypt_blocks (10.84%); ring_core_0_17_14__aes_gcm_enc_update_vaes_avx2 (7.90%) |
| 10 | 17 | ring_core_0_17_14__ChaCha20_ctr32_avx2 (9.71%); quinn_proto::connection::Connection::poll_transmit (9.34%); ring_core_0_17_14__aes_gcm_enc_update_vaes_avx2 (8.93%); quinn_proto::connection::Connection::write_crypto (8.35%); quinn_proto::connection::Connection::init_0rtt (8.33%) |
| 01 | 14 | ring_core_0_17_14__aes_hw_ctr32_encrypt_blocks (12.24%); quinn::endpoint::RecvState::poll_socket (11.89%); <rustls::error::Error as core::clone::Clone>::clone (11.06%); tokio::sync::oneshot::State::set_complete (9.57%); quinn_proto::connection::Connection::populate_packet (7.30%) |
| 11 | 15 | quinn_proto::connection::Connection::process_early_payload (13.65%); <quinn_proto::bloom_token_log::BloomTokenLog as quinn_proto::token::TokenLog>::check_and_insert (12.94%); <rustls::msgs::handshake::CertificateRequestExtensions as rustls::msgs::codec::Codec>::encode (12.08%); quinn_proto::connection::Connection::populate_packet (11.08%); <quinn_proto::frame::FrameType as core::fmt::Display>::fmt (10.64%) |

Build IDs for the profiled executable:
00=d5de696e05782b263adc761df7efb1ffc9ec2e04; 10=d5de696e05782b263adc761df7efb1ffc9ec2e04; 01=d5de696e05782b263adc761df7efb1ffc9ec2e04; 11=d5de696e05782b263adc761df7efb1ffc9ec2e04

The samples are symbolized and include QUIC connection processing (`quinn_proto`), endpoint receive/transmit code, Tokio synchronization, Rustls, and `ring` AES/ChaCha routines. Only 14--17 samples were collected per cell, so these are weak candidate-path evidence. The static main-module comparison reports no LLVM-IR or assembly module changes, and the profile cannot establish a DataflowConstProp/tail-call mechanism.

## Evidence boundary

The profiles use supplemental WSL builds and smoke commands, whereas the historical Δ, confidence intervals, and q-values come from the frozen statistical experiment. Source revisions, toolchains, command inputs, and binary identities were not demonstrated to be identical. Accordingly, the results support path localization and consistency checks only. A causal statement would require matched historical binaries, function-level MIR/LLVM-IR/assembly diffs, and optimization remarks tied to a sampled hot function. Where that mapping is absent, the appropriate wording is that the observed representation differences are consistent with a candidate explanation, not that they prove it.

Static compiler-evidence source: `D:\MIR_LLVM_NEW\large_delta_case_studies\evidence\representative_runs\run_20261023_full_graph\analysis\representative_compiler_evidence.md`
Machine-readable profile source: `D:\MIR_LLVM_NEW\large_delta_case_studies\evidence\hot_paths_wsl_20261105\hot_path_symbolized.csv`