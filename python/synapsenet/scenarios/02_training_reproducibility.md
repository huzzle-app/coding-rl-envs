# Scenario 02: Training Reproducibility Crisis

## Slack Thread: #ml-platform-support

---

**Dr. Sarah Chen** (Principal Data Scientist) - 9:17 AM

@ml-platform-team We have a serious reproducibility problem. I'm running the exact same training job twice with the same hyperparameters and seed, and getting completely different results. This is blocking our paper submission.

---

**Dr. Sarah Chen** - 9:19 AM

Details:
- Model: `fraud-detection-v3`
- Experiment IDs: `exp-a1b2c3` and `exp-d4e5f6`
- Both have `seed: 42` in hyperparameters
- Training data: `dataset-fraud-2024Q1` (identical)
- Final AUC: 0.923 vs 0.891 (that's a HUGE difference)

---

**Marcus Johnson** (ML Platform) - 9:24 AM

Hi Sarah, let me check. Are you using data augmentation?

---

**Dr. Sarah Chen** - 9:26 AM

Yes, standard augmentation pipeline. But the seed should make that deterministic, right?

---

**Marcus Johnson** - 9:31 AM

Checking the experiment tracking service... I see both experiments have `seed: 42` stored. Let me look at the training worker logs.

---

**Dr. Sarah Chen** - 9:35 AM

Also noticed something weird - when I compare epochs, the validation metrics start diverging from epoch 1. It's not a convergence issue late in training. The data ordering seems different from the start.

---

**Priya Patel** (Senior MLE) - 9:42 AM

@sarah I've seen something similar before. What does your data iteration look like? Is the data shuffled between epochs?

---

**Dr. Sarah Chen** - 9:45 AM

I'd expect the data to be shuffled, but deterministically based on the seed. Otherwise every epoch would see the same order which is also bad. Let me check...

Actually, I just ran 2 epochs on a small dataset and printed the batch order. The data IS in the same order every epoch. That can't be right.

---

**Marcus Johnson** - 9:51 AM

Interesting. So we have two issues:
1. Runs with same seed produce different results
2. Data order is identical across epochs (no shuffling)

Let me check the `TrainingDataIterator` and `DataAugmenter` classes.

---

**Dr. Sarah Chen** - 9:58 AM

Wait, I found something in the experiment comparison. Even though I set the same hyperparameters including seed, the actual augmented samples are completely different between the two runs. The augmentation isn't respecting the seed.

Printed some augmented samples:
- Run 1: `[0.342, -0.156, 0.891, ...]`
- Run 2: `[0.087, 0.445, -0.221, ...]`

Same input sample, same seed, different output. This is definitely a platform bug.

---

**Lin Wei** (Data Science Manager) - 10:05 AM

This is blocking 3 different research projects. We need deterministic training for:
1. Regulatory compliance (must reproduce model decisions)
2. Paper reproducibility
3. A/B test validity (need identical control models)

What's the ETA for a fix?

---

**Marcus Johnson** - 10:12 AM

Investigating now. Confirmed issues:
1. `DataAugmenter` accepts a seed parameter but appears to not use it
2. `TrainingDataIterator.reset()` doesn't shuffle the dataset
3. The experiment's seed is set in `ExperimentManager.create_experiment()` but only affects the current process

If training spawns worker processes, they wouldn't inherit the seed state...

---

**Dr. Sarah Chen** - 10:18 AM

So to summarize what's broken:
- Can't reproduce results even with explicit seed
- Data not shuffled between epochs (hurts generalization)
- Augmentation is random each time regardless of seed setting

This is really bad. We've been running experiments for 3 months thinking they were reproducible.

---

## Symptoms Summary

1. **Non-deterministic training** - Same seed produces different final metrics
2. **Static data ordering** - No shuffling between epochs
3. **Augmentation randomness** - Seed parameter ignored in data augmentation
4. **Seed isolation** - Seed only affects main process, not worker processes
5. **Epoch consistency** - Batch ordering identical every epoch

---

## Impact

- 3 research projects blocked
- Regulatory compliance at risk
- 3 months of experiments may not be reproducible
- A/B testing validity questionable
