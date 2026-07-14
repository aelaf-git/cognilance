use anchor_lang::prelude::*;

#[event]
pub struct EscrowReleased {
    pub task_id: u64,
    pub agent_cut: u64,
    pub platform_cut: u64,
    pub agent_wallet: Pubkey,
    pub treasury: Pubkey,
}

#[event]
pub struct EscrowRefunded {
    pub task_id: u64,
    pub amount: u64,
    pub payer: Pubkey,
}
