# T-128 RED criterion → test map

| AC | Test |
|----|------|
| mask_from_channels 12 combos | `test_mask_from_channels_all_twelve_combos` |
| preset round-trip | `test_preset_round_trip_matches_mask_for_without_age` |
| F2 pack_date not age | `test_f2_preset_uses_pack_date_not_age` |
| cache key | `test_channels_cache_key_canonical` |
| invalid enum | `test_validate_channels_rejects_unknown_enum` |
| session RPC | `test_set_obs_channels_on_session` |

RED proof: `uv run pytest tests/test_t128_obs_channels.py --no-cov` (imports fail until implement).
