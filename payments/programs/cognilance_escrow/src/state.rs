use anchor_lang::prelude::*;

pub const CONFIG_SEED: &[u8] = b"config";
pub const ESCROW_SEED: &[u8] = b"escrow";

/// Global config, written once at program initialization.
#[account]
#[derive(InitSpace)]
pub struct Config {
    /// The only key allowed to call release_escrow / refund_escrow.
    pub authority: Pubkey,
    /// Fixed platform treasury wallet (owner of the treasury token account).
    pub treasury: Pubkey,
    pub bump: u8,
}

#[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy, PartialEq, Eq, InitSpace, Debug)]
pub enum EscrowStatus {
    Funded,
    Released,
    Refunded,
}

/// Per-task escrow, seeds = ["escrow", task_id.to_le_bytes()].
#[account]
#[derive(InitSpace)]
pub struct EscrowAccount {
    pub task_id: u64,
    /// Consumer wallet that funded the escrow (refund destination owner).
    pub payer: Pubkey,
    /// Worker agent wallet (release destination owner for the 90% cut).
    pub agent_wallet: Pubkey,
    /// Copied from Config at initialization.
    pub treasury: Pubkey,
    /// Token mint held in the vault (mock/real USDC, 6 decimals).
    pub mint: Pubkey,
    /// Escrowed amount in token base units.
    pub amount: u64,
    pub status: EscrowStatus,
    /// Copied from Config at initialization.
    pub authority: Pubkey,
    pub bump: u8,
}
