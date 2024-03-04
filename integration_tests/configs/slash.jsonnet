local default = import 'accounts.jsonnet';
local genesis = import 'genesis.jsonnet';

{
  validators: [{
    coins: value,
    staked: value,
    min_self_delegation: 10000000,  // 0.1cro
    client_config: {
      'broadcast-mode': 'block',
    },
  } for value in ['40cro', '10cro', '10cro']],
  accounts: default.accounts + default.reserves + default.signers,
  genesis: {
    app_state: {
      staking: genesis.app_state.staking,
      slashing: {
        params: {
          signed_blocks_window: '2',
          slash_fraction_downtime: '0.1',
          downtime_jail_duration: '60s',
        },
      },
    },
  },
}
