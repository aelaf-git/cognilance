pub mod errors;
pub mod events;
pub mod instructions;
pub mod state;

use anchor_lang::prelude::*;

pub use instructions::*;
pub use state::*;

declare_id!("4RMjtWR5LStRJu1HacVNpjmNtuhnRvfG2egDpFW9Rc74");

#[program]
pub mod cognilance_escrow {
    use super::*;

    /// One-time setup: stores the backend authority and treasury pubkeys in a
    /// global config PDA so they can never be redirected per-instruction.
    pub fn initialize_program(
        ctx: Context<InitializeProgram>,
        authority: Pubkey,
        treasury: Pubkey,
    ) -> Result<()> {
        instructions::initialize_program::handle_initialize_program(ctx, authority, treasury)
    }

    /// Creates the per-task escrow PDA and moves `amount` of the token from the
    /// payer's ATA into the escrow vault. Signer: payer.
    pub fn initialize_escrow(
        ctx: Context<InitializeEscrow>,
        task_id: u64,
        amount: u64,
    ) -> Result<()> {
        instructions::initialize_escrow::handle_initialize_escrow(ctx, task_id, amount)
    }

    /// Splits the escrowed amount 90/10 between the agent and the treasury.
    /// Only callable by the configured authority while status is Funded.
    pub fn release_escrow(ctx: Context<ReleaseEscrow>) -> Result<()> {
        instructions::release_escrow::handle_release_escrow(ctx)
    }

    /// Returns the full escrowed amount to the payer.
    /// Only callable by the configured authority while status is Funded.
    pub fn refund_escrow(ctx: Context<RefundEscrow>) -> Result<()> {
        instructions::refund_escrow::handle_refund_escrow(ctx)
    }
}
