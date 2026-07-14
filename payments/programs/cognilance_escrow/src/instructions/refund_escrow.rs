use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};

use crate::errors::EscrowError;
use crate::events::EscrowRefunded;
use crate::state::{Config, EscrowAccount, EscrowStatus, CONFIG_SEED, ESCROW_SEED};

#[derive(Accounts)]
pub struct RefundEscrow<'info> {
    /// Must be the authority stored in the global config.
    pub authority: Signer<'info>,
    #[account(
        seeds = [CONFIG_SEED],
        bump = config.bump,
        has_one = authority @ EscrowError::Unauthorized,
    )]
    pub config: Account<'info, Config>,
    #[account(
        mut,
        seeds = [ESCROW_SEED, escrow.task_id.to_le_bytes().as_ref()],
        bump = escrow.bump,
        has_one = authority @ EscrowError::Unauthorized,
        constraint = escrow.status == EscrowStatus::Funded @ EscrowError::InvalidStatus,
    )]
    pub escrow: Account<'info, EscrowAccount>,
    #[account(
        mut,
        associated_token::mint = escrow.mint,
        associated_token::authority = escrow,
    )]
    pub escrow_vault: Account<'info, TokenAccount>,
    #[account(
        mut,
        token::mint = escrow.mint,
        constraint = payer_token_account.owner == escrow.payer @ EscrowError::Unauthorized,
    )]
    pub payer_token_account: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
}

pub fn handle_refund_escrow(ctx: Context<RefundEscrow>) -> Result<()> {
    let escrow = &ctx.accounts.escrow;
    let amount = escrow.amount;

    let task_id_bytes = escrow.task_id.to_le_bytes();
    let signer_seeds: &[&[&[u8]]] = &[&[ESCROW_SEED, task_id_bytes.as_ref(), &[escrow.bump]]];

    token::transfer(
        CpiContext::new_with_signer(
            ctx.accounts.token_program.key(),
            Transfer {
                from: ctx.accounts.escrow_vault.to_account_info(),
                to: ctx.accounts.payer_token_account.to_account_info(),
                authority: ctx.accounts.escrow.to_account_info(),
            },
            signer_seeds,
        ),
        amount,
    )?;

    let escrow = &mut ctx.accounts.escrow;
    escrow.status = EscrowStatus::Refunded;

    emit!(EscrowRefunded {
        task_id: escrow.task_id,
        amount,
        payer: escrow.payer,
    });

    Ok(())
}
