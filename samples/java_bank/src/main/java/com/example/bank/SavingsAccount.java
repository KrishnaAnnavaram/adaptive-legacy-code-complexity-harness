package com.example.bank;

/**
 * Account that accrues interest via a pluggable policy. Demonstrates inheritance
 * (extends Account), an overridden method, a bounded loop, a ternary, and a call
 * through an interface (InterestPolicy).
 */
public class SavingsAccount extends Account {

    private final InterestPolicy policy;

    public SavingsAccount(String id, String owner, double opening, InterestPolicy policy) {
        super(id, owner, opening);
        this.policy = policy;
    }

    public void applyInterest(int months) {
        for (int month = 1; month <= months; month++) {
            double gain = balance * policy.rate(month);
            balance += gain;
        }
        audit("INTEREST");
    }

    @Override
    public void withdraw(double amount) {
        double fee = amount > 1000 ? 5.0 : 0.0;
        super.withdraw(amount + fee);
    }
}
