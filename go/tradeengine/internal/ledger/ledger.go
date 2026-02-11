package ledger

import (
	"context"
	"database/sql"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/shopspring/decimal"
	"github.com/terminal-bench/tradeengine/pkg/messaging"
)

// Ledger implements a double-entry accounting ledger
type Ledger struct {
	db        *sql.DB
	msgClient *messaging.Client
	
	mu        sync.RWMutex
}

// Account represents a ledger account
type Account struct {
	ID        uuid.UUID
	UserID    uuid.UUID
	Type      string // "asset", "liability", "equity", "revenue", "expense"
	Currency  string
	Balance   decimal.Decimal
	Available decimal.Decimal
	Hold      decimal.Decimal
	CreatedAt time.Time
	UpdatedAt time.Time
	Version   int
}

// Entry represents a ledger entry
type Entry struct {
	ID          uuid.UUID
	AccountID   uuid.UUID
	Type        string // "debit" or "credit"
	Amount      decimal.Decimal
	Balance     decimal.Decimal
	Reference   string
	Description string
	Metadata    map[string]string
	CreatedAt   time.Time
}

// Transfer represents a transfer between accounts
type Transfer struct {
	ID            uuid.UUID
	FromAccountID uuid.UUID
	ToAccountID   uuid.UUID
	Amount        decimal.Decimal
	Currency      string
	Reference     string
	Status        string
	CreatedAt     time.Time
	CompletedAt   *time.Time
}

// NewLedger creates a new ledger
func NewLedger(db *sql.DB, msgClient *messaging.Client) *Ledger {
	return &Ledger{
		db:        db,
		msgClient: msgClient,
	}
}

// CreateAccount creates a new account
func (l *Ledger) CreateAccount(ctx context.Context, userID uuid.UUID, accountType, currency string) (*Account, error) {
	account := &Account{
		ID:        uuid.New(),
		UserID:    userID,
		Type:      accountType,
		Currency:  currency,
		Balance:   decimal.Zero,
		Available: decimal.Zero,
		Hold:      decimal.Zero,
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
		Version:   1,
	}

	_, err := l.db.ExecContext(ctx,
		`INSERT INTO accounts (id, user_id, type, currency, balance, available, hold, created_at, updated_at, version)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
		account.ID, account.UserID, account.Type, account.Currency,
		account.Balance, account.Available, account.Hold,
		account.CreatedAt, account.UpdatedAt, account.Version,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create account: %w", err)
	}

	return account, nil
}

// GetAccount retrieves an account
func (l *Ledger) GetAccount(ctx context.Context, accountID uuid.UUID) (*Account, error) {
	var account Account
	err := l.db.QueryRowContext(ctx,
		`SELECT id, user_id, type, currency, balance, available, hold, created_at, updated_at, version
		 FROM accounts WHERE id = $1`,
		accountID,
	).Scan(&account.ID, &account.UserID, &account.Type, &account.Currency,
		&account.Balance, &account.Available, &account.Hold,
		&account.CreatedAt, &account.UpdatedAt, &account.Version)

	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("account not found")
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get account: %w", err)
	}

	return &account, nil
}

// Credit credits an account (increases balance)
func (l *Ledger) Credit(ctx context.Context, accountID uuid.UUID, amount decimal.Decimal, reference, description string) (*Entry, error) {
	return l.createEntry(ctx, accountID, "credit", amount, reference, description)
}

// Debit debits an account (decreases balance)
func (l *Ledger) Debit(ctx context.Context, accountID uuid.UUID, amount decimal.Decimal, reference, description string) (*Entry, error) {
	return l.createEntry(ctx, accountID, "debit", amount, reference, description)
}

func (l *Ledger) createEntry(ctx context.Context, accountID uuid.UUID, entryType string, amount decimal.Decimal, reference, description string) (*Entry, error) {
	tx, err := l.db.BeginTx(ctx, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to begin transaction: %w", err)
	}
	
	defer tx.Rollback()

	// Lock the account row
	var account Account
	err = tx.QueryRowContext(ctx,
		`SELECT id, user_id, type, currency, balance, available, hold, version
		 FROM accounts WHERE id = $1 FOR UPDATE`,
		accountID,
	).Scan(&account.ID, &account.UserID, &account.Type, &account.Currency,
		&account.Balance, &account.Available, &account.Hold, &account.Version)

	if err != nil {
		return nil, fmt.Errorf("failed to lock account: %w", err)
	}

	// Calculate new balance
	var newBalance decimal.Decimal
	if entryType == "credit" {
		newBalance = account.Balance.Add(amount)
	} else {
		newBalance = account.Balance.Sub(amount)
		
		if newBalance.LessThan(decimal.Zero) {
			return nil, fmt.Errorf("insufficient balance")
		}
	}

	// Create entry
	entry := &Entry{
		ID:          uuid.New(),
		AccountID:   accountID,
		Type:        entryType,
		Amount:      amount,
		Balance:     newBalance,
		Reference:   reference,
		Description: description,
		CreatedAt:   time.Now(),
	}

	// Insert entry
	_, err = tx.ExecContext(ctx,
		`INSERT INTO entries (id, account_id, type, amount, balance, reference, description, created_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
		entry.ID, entry.AccountID, entry.Type, entry.Amount,
		entry.Balance, entry.Reference, entry.Description, entry.CreatedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create entry: %w", err)
	}

	// Update account balance
	
	result, err := tx.ExecContext(ctx,
		`UPDATE accounts SET balance = $1, available = $2, updated_at = $3, version = version + 1
		 WHERE id = $4 AND version = $5`,
		newBalance, newBalance.Sub(account.Hold), time.Now(), accountID, account.Version,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to update account: %w", err)
	}

	rows, _ := result.RowsAffected()
	if rows == 0 {
		
		return nil, fmt.Errorf("concurrent modification detected")
	}

	if err := tx.Commit(); err != nil {
		return nil, fmt.Errorf("failed to commit: %w", err)
	}

	// Publish event
	l.publishEntryEvent(ctx, entry)

	return entry, nil
}

// Transfer transfers funds between accounts
func (l *Ledger) Transfer(ctx context.Context, fromID, toID uuid.UUID, amount decimal.Decimal, reference string) (*Transfer, error) {
	tx, err := l.db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelSerializable})
	if err != nil {
		return nil, fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	
	// to prevent deadlocks. Here we lock in parameter order which may vary.

	// Lock from account
	var fromAccount Account
	err = tx.QueryRowContext(ctx,
		`SELECT id, balance, available, version FROM accounts WHERE id = $1 FOR UPDATE`,
		fromID,
	).Scan(&fromAccount.ID, &fromAccount.Balance, &fromAccount.Available, &fromAccount.Version)
	if err != nil {
		return nil, fmt.Errorf("failed to lock from account: %w", err)
	}

	// Lock to account
	var toAccount Account
	err = tx.QueryRowContext(ctx,
		`SELECT id, balance, available, version FROM accounts WHERE id = $1 FOR UPDATE`,
		toID,
	).Scan(&toAccount.ID, &toAccount.Balance, &toAccount.Available, &toAccount.Version)
	if err != nil {
		return nil, fmt.Errorf("failed to lock to account: %w", err)
	}

	// Check sufficient balance
	if fromAccount.Available.LessThan(amount) {
		return nil, fmt.Errorf("insufficient available balance")
	}

	// Create transfer record
	transfer := &Transfer{
		ID:            uuid.New(),
		FromAccountID: fromID,
		ToAccountID:   toID,
		Amount:        amount,
		Reference:     reference,
		Status:        "completed",
		CreatedAt:     time.Now(),
	}
	now := time.Now()
	transfer.CompletedAt = &now

	// Debit from account
	newFromBalance := fromAccount.Balance.Sub(amount)
	_, err = tx.ExecContext(ctx,
		`UPDATE accounts SET balance = $1, available = $2, updated_at = $3, version = version + 1
		 WHERE id = $4`,
		newFromBalance, newFromBalance, time.Now(), fromID,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to debit account: %w", err)
	}

	// Credit to account
	newToBalance := toAccount.Balance.Add(amount)
	_, err = tx.ExecContext(ctx,
		`UPDATE accounts SET balance = $1, available = $2, updated_at = $3, version = version + 1
		 WHERE id = $4`,
		newToBalance, newToBalance, time.Now(), toID,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to credit account: %w", err)
	}

	// Insert transfer record
	_, err = tx.ExecContext(ctx,
		`INSERT INTO transfers (id, from_account_id, to_account_id, amount, reference, status, created_at, completed_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
		transfer.ID, transfer.FromAccountID, transfer.ToAccountID,
		transfer.Amount, transfer.Reference, transfer.Status,
		transfer.CreatedAt, transfer.CompletedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create transfer: %w", err)
	}

	// Create ledger entries for audit
	
	l.createEntryInTx(tx, ctx, fromID, "debit", amount, reference, "Transfer out")
	l.createEntryInTx(tx, ctx, toID, "credit", amount, reference, "Transfer in")

	if err := tx.Commit(); err != nil {
		return nil, fmt.Errorf("failed to commit: %w", err)
	}

	return transfer, nil
}

func (l *Ledger) createEntryInTx(tx *sql.Tx, ctx context.Context, accountID uuid.UUID, entryType string, amount decimal.Decimal, reference, description string) error {
	entry := &Entry{
		ID:          uuid.New(),
		AccountID:   accountID,
		Type:        entryType,
		Amount:      amount,
		Reference:   reference,
		Description: description,
		CreatedAt:   time.Now(),
	}

	_, err := tx.ExecContext(ctx,
		`INSERT INTO entries (id, account_id, type, amount, reference, description, created_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7)`,
		entry.ID, entry.AccountID, entry.Type, entry.Amount,
		entry.Reference, entry.Description, entry.CreatedAt,
	)

	return err
}

// Hold places a hold on funds
func (l *Ledger) Hold(ctx context.Context, accountID uuid.UUID, amount decimal.Decimal, reference string) error {
	tx, err := l.db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	var account Account
	err = tx.QueryRowContext(ctx,
		`SELECT id, balance, available, hold, version FROM accounts WHERE id = $1 FOR UPDATE`,
		accountID,
	).Scan(&account.ID, &account.Balance, &account.Available, &account.Hold, &account.Version)
	if err != nil {
		return fmt.Errorf("failed to lock account: %w", err)
	}

	if account.Available.LessThan(amount) {
		return fmt.Errorf("insufficient available balance for hold")
	}

	newAvailable := account.Available.Sub(amount)
	newHold := account.Hold.Add(amount)

	_, err = tx.ExecContext(ctx,
		`UPDATE accounts SET available = $1, hold = $2, updated_at = $3, version = version + 1
		 WHERE id = $4`,
		newAvailable, newHold, time.Now(), accountID,
	)
	if err != nil {
		return fmt.Errorf("failed to update account: %w", err)
	}

	return tx.Commit()
}

// ReleaseHold releases a hold
func (l *Ledger) ReleaseHold(ctx context.Context, accountID uuid.UUID, amount decimal.Decimal) error {
	tx, err := l.db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	var account Account
	err = tx.QueryRowContext(ctx,
		`SELECT id, balance, available, hold, version FROM accounts WHERE id = $1 FOR UPDATE`,
		accountID,
	).Scan(&account.ID, &account.Balance, &account.Available, &account.Hold, &account.Version)
	if err != nil {
		return fmt.Errorf("failed to lock account: %w", err)
	}

	if account.Hold.LessThan(amount) {
		return fmt.Errorf("hold amount exceeds current hold")
	}

	newAvailable := account.Available.Add(amount)
	newHold := account.Hold.Sub(amount)

	_, err = tx.ExecContext(ctx,
		`UPDATE accounts SET available = $1, hold = $2, updated_at = $3, version = version + 1
		 WHERE id = $4`,
		newAvailable, newHold, time.Now(), accountID,
	)
	if err != nil {
		return fmt.Errorf("failed to update account: %w", err)
	}

	return tx.Commit()
}

func (l *Ledger) publishEntryEvent(ctx context.Context, entry *Entry) {
	event := messaging.LedgerEntryEvent{
		EntryID:     entry.ID,
		AccountID:   entry.AccountID,
		Type:        entry.Type,
		Amount:      entry.Amount.String(),
		Balance:     entry.Balance.String(),
		Reference:   entry.Reference,
		Description: entry.Description,
	}

	
	l.msgClient.Publish(ctx, messaging.EventTypeLedgerEntry, event)
}

// GetEntries returns entries for an account
func (l *Ledger) GetEntries(ctx context.Context, accountID uuid.UUID, limit int) ([]Entry, error) {
	
	rows, err := l.db.QueryContext(ctx,
		`SELECT id, account_id, type, amount, balance, reference, description, created_at
		 FROM entries WHERE account_id = $1 ORDER BY created_at DESC LIMIT $2`,
		accountID, limit,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to query entries: %w", err)
	}

	var entries []Entry
	for rows.Next() {
		var entry Entry
		err := rows.Scan(&entry.ID, &entry.AccountID, &entry.Type, &entry.Amount,
			&entry.Balance, &entry.Reference, &entry.Description, &entry.CreatedAt)
		if err != nil {
			
			return nil, fmt.Errorf("failed to scan entry: %w", err)
		}
		entries = append(entries, entry)
	}
	rows.Close()

	return entries, nil
}
