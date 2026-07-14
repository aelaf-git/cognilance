use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};

use crate::errors::EscrowError;
use crate::events::EscrowReleased;
use crate::state::{Config, EscrowAccount, EscrowStatus, CONFIG_SEED, ESCROW_SEED};

#[derive(Accounts)]
pub struct ReleaseEscrow<'info> {
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
        constraint = agent_token_account.owner == escrow.agent_wallet @ EscrowError::Unauthorized,
    )]
    pub agent_token_account: Account<'info, TokenAccount>,
    #[account(
        mut,
        token::mint = escrow.mint,
        constraint = treasury_token_account.owner == escrow.treasury @ EscrowError::Unauthorized,
    )]
    pub treasury_token_account: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
}

pub fn handle_release_escrow(ctx: Context<ReleaseEscrow>) -> Result<()> {
    let escrow = &ctx.accounts.escrow;
    let amount = escrow.amount;

    // 90/10 split in integer base units. The platform cut takes the remainder
    // so agent_cut + platform_cut == amount exactly (no rounding dust).
    let agent_cut = u64::try_from(
        (amount as u128)
            .checked_mul(90)
            .ok_or(EscrowError::MathOverflow)?
            / 100,
    )
    .map_err(|_| EscrowError::MathOverflow)?;
    let platform_cut = amount - agent_cut;

    let task_id_bytes = escrow.task_id.to_le_bytes();
    let signer_seeds: &[&[&[u8]]] = &[&[ESCROW_SEED, task_id_bytes.as_ref(), &[escrow.bump]]];

    if agent_cut > 0 {
        token::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.key(),
                Transfer {
                    from: ctx.accounts.escrow_vault.to_account_info(),
                    to: ctx.accounts.agent_token_account.to_account_info(),
                    authority: ctx.accounts.escrow.to_account_info(),
                },
                signer_seeds,
            ),
            agent_cut,
        )?;
    }
    if platform_cut > 0 {
        token::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.key(),
                Transfer {
                    from: ctx.accounts.escrow_vault.to_account_info(),
                    to: ctx.accounts.treasury_token_account.to_account_info(),
                    authority: ctx.accounts.escrow.to_account_info(),
                },
                signer_seeds,
            ),
            platform_cut,
        )?;
    }

    let escrow = &mut ctx.accounts.escrow;
    escrow.status = EscrowStatus::Released;

    emit!(EscrowReleased {
        task_id: escrow.task_id,
        agent_cut,
        platform_cut,
        agent_wallet: escrow.agent_wallet,
        treasury: escrow.treasury,
    });

    Ok(())
}
