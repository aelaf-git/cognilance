import * as anchor from "@anchor-lang/core";
import { AnchorError, BN, Program } from "@anchor-lang/core";
import {
  Keypair,
  LAMPORTS_PER_SOL,
  PublicKey,
  SystemProgram,
} from "@solana/web3.js";
import {
  TOKEN_PROGRAM_ID,
  ASSOCIATED_TOKEN_PROGRAM_ID,
  createMint,
  getAssociatedTokenAddressSync,
  getOrCreateAssociatedTokenAccount,
  getAccount,
  mintTo,
} from "@solana/spl-token";
import { assert } from "chai";
import { CognilanceEscrow } from "../target/types/cognilance_escrow";

// All amounts in this file are integer USDC base units (6 decimals). No floats.
const USDC_DECIMALS = 6;

describe("cognilance_escrow", () => {
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);
  const program = anchor.workspace
    .cognilanceEscrow as Program<CognilanceEscrow>;
  const connection = provider.connection;

  // Wallets
  const authority = Keypair.generate(); // backend signer
  const nonAuthority = Keypair.generate(); // attacker
  const payer = Keypair.generate(); // consumer
  const agent = Keypair.generate(); // worker agent
  const treasury = Keypair.generate(); // platform treasury

  let mint: PublicKey;
  let payerAta: PublicKey;
  let agentAta: PublicKey;
  let treasuryAta: PublicKey;

  const [configPda] = PublicKey.findProgramAddressSync(
    [Buffer.from("config")],
    program.programId
  );

  const escrowPda = (taskId: BN) =>
    PublicKey.findProgramAddressSync(
      [Buffer.from("escrow"), taskId.toArrayLike(Buffer, "le", 8)],
      program.programId
    )[0];

  const vaultFor = (escrow: PublicKey) =>
    getAssociatedTokenAddressSync(mint, escrow, true);

  const tokenBalance = async (ata: PublicKey): Promise<bigint> =>
    (await getAccount(connection, ata)).amount;

  const initializeEscrow = async (taskId: BN, amount: BN) =>
    program.methods
      .initializeEscrow(taskId, amount)
      .accountsPartial({
        payer: payer.publicKey,
        agentWallet: agent.publicKey,
        config: configPda,
        mint,
        escrow: escrowPda(taskId),
        escrowVault: vaultFor(escrowPda(taskId)),
        payerTokenAccount: payerAta,
        tokenProgram: TOKEN_PROGRAM_ID,
        associatedTokenProgram: ASSOCIATED_TOKEN_PROGRAM_ID,
        systemProgram: SystemProgram.programId,
      })
      .signers([payer])
      .rpc();

  const releaseEscrow = async (taskId: BN, signer: Keypair) =>
    program.methods
      .releaseEscrow()
      .accountsPartial({
        authority: signer.publicKey,
        config: configPda,
        escrow: escrowPda(taskId),
        escrowVault: vaultFor(escrowPda(taskId)),
        agentTokenAccount: agentAta,
        treasuryTokenAccount: treasuryAta,
        tokenProgram: TOKEN_PROGRAM_ID,
      })
      .signers([signer])
      .rpc();

  const refundEscrow = async (taskId: BN, signer: Keypair) =>
    program.methods
      .refundEscrow()
      .accountsPartial({
        authority: signer.publicKey,
        config: configPda,
        escrow: escrowPda(taskId),
        escrowVault: vaultFor(escrowPda(taskId)),
        payerTokenAccount: payerAta,
        tokenProgram: TOKEN_PROGRAM_ID,
      })
      .signers([signer])
      .rpc();

  const expectAnchorError = async (
    promise: Promise<unknown>,
    errorCode: string
  ) => {
    try {
      await promise;
      assert.fail(`expected ${errorCode}, but transaction succeeded`);
    } catch (err) {
      assert.instanceOf(err, AnchorError, `expected AnchorError, got: ${err}`);
      assert.strictEqual((err as AnchorError).error.errorCode.code, errorCode);
    }
  };

  before(async () => {
    // Fund fee payers.
    for (const kp of [authority, nonAuthority, payer]) {
      const sig = await connection.requestAirdrop(
        kp.publicKey,
        10 * LAMPORTS_PER_SOL
      );
      await connection.confirmTransaction(sig, "confirmed");
    }

    // Mock USDC mint + token accounts (mirrors scripts/create-mock-usdc.ts).
    mint = await createMint(
      connection,
      payer,
      payer.publicKey,
      null,
      USDC_DECIMALS
    );
    payerAta = (
      await getOrCreateAssociatedTokenAccount(
        connection,
        payer,
        mint,
        payer.publicKey
      )
    ).address;
    agentAta = (
      await getOrCreateAssociatedTokenAccount(
        connection,
        payer,
        mint,
        agent.publicKey
      )
    ).address;
    treasuryAta = (
      await getOrCreateAssociatedTokenAccount(
        connection,
        payer,
        mint,
        treasury.publicKey
      )
    ).address;
    // 1,000,000 mock USDC in base units.
    await mintTo(connection, payer, mint, payerAta, payer, 1_000_000_000_000n);

    await program.methods
      .initializeProgram(authority.publicKey, treasury.publicKey)
      .accountsPartial({
        payer: provider.wallet.publicKey,
        config: configPda,
        systemProgram: SystemProgram.programId,
      })
      .rpc();
  });

  it("stores authority and treasury in the config PDA", async () => {
    const config = await program.account.config.fetch(configPda);
    assert.strictEqual(
      config.authority.toBase58(),
      authority.publicKey.toBase58()
    );
    assert.strictEqual(
      config.treasury.toBase58(),
      treasury.publicKey.toBase58()
    );
  });

  it("happy path: fund then release with exact 90/10 split", async () => {
    const taskId = new BN(1);
    const amount = new BN(1_000_000); // 1 USDC

    const payerBefore = await tokenBalance(payerAta);
    await initializeEscrow(taskId, amount);

    // Funding moved the exact amount into the vault.
    assert.strictEqual(await tokenBalance(payerAta), payerBefore - 1_000_000n);
    assert.strictEqual(await tokenBalance(vaultFor(escrowPda(taskId))), 1_000_000n);

    let escrow = await program.account.escrowAccount.fetch(escrowPda(taskId));
    assert.isDefined(escrow.status.funded);
    assert.strictEqual(escrow.amount.toString(), "1000000");
    assert.strictEqual(escrow.payer.toBase58(), payer.publicKey.toBase58());
    assert.strictEqual(
      escrow.agentWallet.toBase58(),
      agent.publicKey.toBase58()
    );

    const agentBefore = await tokenBalance(agentAta);
    const treasuryBefore = await tokenBalance(treasuryAta);
    await releaseEscrow(taskId, authority);

    assert.strictEqual(await tokenBalance(agentAta), agentBefore + 900_000n);
    assert.strictEqual(
      await tokenBalance(treasuryAta),
      treasuryBefore + 100_000n
    );
    assert.strictEqual(await tokenBalance(vaultFor(escrowPda(taskId))), 0n);

    escrow = await program.account.escrowAccount.fetch(escrowPda(taskId));
    assert.isDefined(escrow.status.released);
  });

  it("non-round amount: remainder goes to the platform (101 -> 90 / 11)", async () => {
    const taskId = new BN(2);
    await initializeEscrow(taskId, new BN(101));

    const agentBefore = await tokenBalance(agentAta);
    const treasuryBefore = await tokenBalance(treasuryAta);
    await releaseEscrow(taskId, authority);

    assert.strictEqual(await tokenBalance(agentAta), agentBefore + 90n);
    assert.strictEqual(await tokenBalance(treasuryAta), treasuryBefore + 11n);
    assert.strictEqual(await tokenBalance(vaultFor(escrowPda(taskId))), 0n);
  });

  it("refund path: full amount returns to the payer", async () => {
    const taskId = new BN(3);
    const payerBefore = await tokenBalance(payerAta);
    await initializeEscrow(taskId, new BN(123_456));
    assert.strictEqual(await tokenBalance(payerAta), payerBefore - 123_456n);

    await refundEscrow(taskId, authority);
    assert.strictEqual(await tokenBalance(payerAta), payerBefore);
    assert.strictEqual(await tokenBalance(vaultFor(escrowPda(taskId))), 0n);

    const escrow = await program.account.escrowAccount.fetch(escrowPda(taskId));
    assert.isDefined(escrow.status.refunded);
  });

  it("rejects release from a non-authority signer", async () => {
    const taskId = new BN(4);
    await initializeEscrow(taskId, new BN(50_000));
    await expectAnchorError(
      releaseEscrow(taskId, nonAuthority),
      "Unauthorized"
    );
    // Funds stay in the vault.
    assert.strictEqual(await tokenBalance(vaultFor(escrowPda(taskId))), 50_000n);
  });

  it("rejects refund from a non-authority signer", async () => {
    const taskId = new BN(5);
    await initializeEscrow(taskId, new BN(50_000));
    await expectAnchorError(refundEscrow(taskId, nonAuthority), "Unauthorized");
    assert.strictEqual(await tokenBalance(vaultFor(escrowPda(taskId))), 50_000n);
  });

  it("rejects a double release", async () => {
    const taskId = new BN(6);
    await initializeEscrow(taskId, new BN(10_000));
    await releaseEscrow(taskId, authority);
    await expectAnchorError(releaseEscrow(taskId, authority), "InvalidStatus");
  });

  it("rejects release on an already-refunded escrow", async () => {
    const taskId = new BN(7);
    await initializeEscrow(taskId, new BN(10_000));
    await refundEscrow(taskId, authority);
    await expectAnchorError(releaseEscrow(taskId, authority), "InvalidStatus");
    await expectAnchorError(refundEscrow(taskId, authority), "InvalidStatus");
  });

  it("edge case: amount = 1 releases without panicking (agent 0, platform 1)", async () => {
    const taskId = new BN(8);
    await initializeEscrow(taskId, new BN(1));

    const agentBefore = await tokenBalance(agentAta);
    const treasuryBefore = await tokenBalance(treasuryAta);
    await releaseEscrow(taskId, authority);

    assert.strictEqual(await tokenBalance(agentAta), agentBefore);
    assert.strictEqual(await tokenBalance(treasuryAta), treasuryBefore + 1n);
  });

  it("rejects a zero-amount escrow", async () => {
    await expectAnchorError(
      initializeEscrow(new BN(9), new BN(0)),
      "ZeroAmount"
    );
  });
});
