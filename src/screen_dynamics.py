#!/usr/bin/env python

import os
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
import re


# Set settings
pd.set_option("date_dayfirst", True)
sns.set(context="paper", style="white", palette="pastel", color_codes=True)
sns.set_palette(sns.color_palette("colorblind"))
matplotlib.rcParams["svg.fonttype"] = "none"
matplotlib.rc('text', usetex=False)


def filter_gRNAs(df, filter_out=None, prefix=""):
    """
    Filter gRNA table (index) by not included gRNAs
    and gRNAs from opposite library
    """
    filtered = df.copy()

    if filter_out is None:
        filter_out = [  # gRNAs which were not used in the screen
            "CTRL00717", "CTRL00728", "CTRL00783", "CTRL00801",
            "CTRL00851", "CTRL00859", "CTRL00868", "CTRL00872",
            "CTRL00878", "CTRL00881", "CTRL00969", "CTRL00972",
            "CTRL00983"]
        filter_out += [  # gRNAs which were not used in the screen
            "Essential_library_ABL1_1", "Essential_library_ABL1_2", "Essential_library_ABL1_3",
            "Essential_library_MAPK1_1", "Essential_library_MAPK1_2", "Essential_library_MAPK1_3",
            "Essential_library_GATA1_1", "Essential_library_GATA1_2", "Essential_library_GATA1_3",
            "Essential_library_BRCA2_1", "Essential_library_BRCA2_2", "Essential_library_BRCA2_3",
            "Essential_library_PARP1_1", "Essential_library_PARP1_2", "Essential_library_PARP1_3"]

    # Filter non-existing
    df = df.ix[df.index[~df.index.isin(filter_out)]]

    all_ctrls = filtered.index[filtered.index.str.contains("Essential|CTRL")]
    others = all_ctrls[~all_ctrls.isin(filter_out)]
    filtered.loc[others, :] = pd.np.nan

    # Filter opposite library
    for col in df.columns:
        if ('TCR' in col) or ('Jurkat' in col):
            df.loc[df.index[df.index.str.contains("Wnt")].tolist(), col] = pd.np.nan
            filtered.loc[filtered.index[filtered.index.str.contains("Tcr")].tolist(), col] = pd.np.nan
        elif ('WNT' in col) or ('HEK' in col):
            df.loc[df.index[df.index.str.contains("Tcr")].tolist(), col] = pd.np.nan
            filtered.loc[filtered.index[filtered.index.str.contains("Wnt")].tolist(), col] = pd.np.nan

    if "plasmid_pool_ESS" in df.columns:
        df = df.drop("plasmid_pool_ESS", axis=1)
        filtered = filtered.drop("plasmid_pool_ESS", axis=1)

    # Vizualize distribution of noise
    fig, axis = plt.subplots(1)
    x = df.values.reshape((np.product(df.shape), 1))
    sns.distplot(np.log2(1 + x[~np.isnan(x)]), ax=axis, label="True gRNAs")
    x = filtered.values.reshape((np.product(filtered.shape), 1))
    sns.distplot(np.log2(1 + x[~np.isnan(x)]), ax=axis, label="False assignments")

    # plot 95% percentile of noise
    lower_bound = np.percentile(x[~np.isnan(x)], 95)
    axis.axvline(x=np.log2(1 + lower_bound), color='black', linestyle='--', lw=0.5)
    axis.text(x=np.log2(1 + lower_bound), y=0.5, s="95th percentile = {} cells".format(lower_bound))

    axis.set_xlabel("Number of cells assigned (log2)")
    axis.set_ylabel("Density")
    axis.legend()
    sns.despine(fig)
    fig.savefig(os.path.join(results_dir, "gRNA_counts.cell_distribution_noise.{}.svg".format(prefix)), bbox_inches="tight")

    # Filter gRNAs below lower bound
    df = df.where(df > lower_bound, pd.np.nan)

    return df


def normalize_by_total(df):
    """
    Normalize number of gRNA molecules / gRNA-assigned cells by total, experiment-wise.
    """
    return df.apply(lambda x: (x / x.sum()) * 1e4, axis=0)


def screen_zscore(series, axis=None, z_score=False, plot=True):
    """
    """
    Z = lambda pos, neg: 1 - (3 * (np.std(pos) + np.std(neg)) / (abs(np.mean(pos) - np.mean(neg))))

    if z_score:
        series = (series - series.mean()) / series.std()

    pos = series.ix[series.index[series.index.str.contains("Essential")]]
    neg = series.ix[series.index[series.index.str.contains("CTRL")]]

    z = Z(pos, neg)

    # Plot
    if plot:
        pos.name = None
        neg.name = None
        if axis is None:
            fig, axis = plt.subplots(1)
        sns.distplot(pos, ax=axis, label="positive controls")
        sns.distplot(neg, ax=axis, label="negative controls; screen Z-score = {}".format(z))

    return z


def gRNA_scatter(s1, s2, prefix=""):
    # Scatter of gRNA change
    fig, axis = plt.subplots(3, 2, sharex=False, sharey=False, figsize=(8, 8))
    axis = axis.flatten()

    for i, screen in enumerate(s2.columns[::-1]):
        x = s1.join(s2)  # .fillna(0)
        x = x.iloc[np.random.permutation(len(x))]

        if "original" in prefix:
            if "TCR" in screen:
                x = x.ix[x.index[~x.index.str.contains("Wnt")]]
                b = x["plasmid_pool_TCR"]
            if "WNT" in screen:
                x = x.ix[x.index[~x.index.str.contains("Tcr")]]
                b = x["plasmid_pool_WNT"]
        elif "plasmid" not in prefix:
            if "TCR" in screen:
                x = x.ix[x.index[~x.index.str.contains("Wnt")]]
                b = x["gDNA_Jurkat"]
            if "_4_WNT" in screen:
                x = x.ix[x.index[~x.index.str.contains("Tcr")]]
                b = x["gDNA_HEKclone4"]
            if "_6_WNT" in screen:
                x = x.ix[x.index[~x.index.str.contains("Tcr")]]
                b = x["gDNA_HEKclone6"]
        else:
            b = x[0]

        colors = pd.DataFrame()
        colors[sns.color_palette("colorblind")[0]] = x.index.str.contains("Wnt")
        colors[sns.color_palette("colorblind")[1]] = x.index.str.contains("CTRL")
        colors[sns.color_palette("colorblind")[2]] = x.index.str.contains("Tcr")
        colors[sns.color_palette("colorblind")[3]] = x.index.str.contains("Ess")
        colors = colors.apply(lambda x: x[x].index.tolist()[0], axis=1).tolist()

        axis[i].scatter(np.log2(1 + x[screen]), np.log2(1 + b), color=colors, alpha=0.5)

        # x = y line
        lims = [np.nanmin([np.log2(1 + x[screen]), np.log2(1 + b)]), np.nanmax([np.log2(1 + x[screen]), np.log2(1 + b)])]
        axis[i].plot((lims[0], lims[1]), (lims[0], lims[1]), linestyle='--', color='black', alpha=0.75)

        axis[i].set_title(screen)
    for i in range(0, len(axis), 2):
        axis[i].set_ylabel("gRNA frequency in plasmid (log2)")
    for ax in axis[-2:]:
        ax.set_xlabel("gRNA frequency in CROP-seq screen (log2)")
    sns.despine(fig)
    fig.savefig(os.path.join(results_dir, "gRNA_counts.norm.{}.scatter.svg".format(prefix)), bbox_inches="tight")


def gRNA_maplot(s1, s2, prefix=""):
    # Rank of gRNA change
    fig, axis = plt.subplots(3, 2, sharex=True, sharey=True, figsize=(8, 8))
    axis = axis.flatten()

    for i, screen in enumerate(s2.columns[::-1]):
        x = s1.join(s2)  # .fillna(0)
        x = x.iloc[np.random.permutation(len(x))]

        if "original" in prefix:
            if "TCR" in screen:
                x = x.ix[x.index[~x.index.str.contains("Wnt")]]
                M = np.log2(x[screen] * x["plasmid_pool_TCR"]) / 2.
                fc = np.log2(1 + x[screen]) - np.log2(1 + x["plasmid_pool_TCR"])
            if "WNT" in screen:
                x = x.ix[x.index[~x.index.str.contains("Tcr")]]
                M = np.log2(x[screen] * x["plasmid_pool_WNT"]) / 2.
                fc = np.log2(1 + x[screen]) - np.log2(1 + x["plasmid_pool_WNT"])
        elif "plasmid" not in prefix:
            if "TCR" in screen:
                x = x.ix[x.index[~x.index.str.contains("Wnt")]]
                M = np.log2(x[screen] * x["gDNA_Jurkat"]) / 2.
                fc = np.log2(1 + x[screen]) - np.log2(1 + x["gDNA_Jurkat"])
            if "_4_WNT" in screen:
                x = x.ix[x.index[~x.index.str.contains("Tcr")]]
                M = np.log2(x[screen] * x["gDNA_HEKclone4"]) / 2.
                fc = np.log2(1 + x[screen]) - np.log2(1 + x["gDNA_HEKclone4"])
            if "_6_WNT" in screen:
                x = x.ix[x.index[~x.index.str.contains("Tcr")]]
                M = np.log2(x[screen] * x["gDNA_HEKclone6"]) / 2.
                fc = np.log2(1 + x[screen]) - np.log2(1 + x["gDNA_HEKclone6"])
        else:
            M = np.log2((1 + x[screen]) * (1 + x[0])) / 2.
            fc = np.log2(1 + x[screen]) - np.log2(1 + x[0])

        fc.name = screen
        if i == 0:
            xx = pd.DataFrame(fc)
        else:
            xx = xx.join(fc, how="outer")

        colors = pd.DataFrame()
        colors[sns.color_palette("colorblind")[0]] = x.index.str.contains("Wnt")
        colors[sns.color_palette("colorblind")[1]] = x.index.str.contains("CTRL")
        colors[sns.color_palette("colorblind")[2]] = x.index.str.contains("Tcr")
        colors[sns.color_palette("colorblind")[3]] = x.index.str.contains("Ess")
        colors = colors.apply(lambda x: x[x].index.tolist()[0], axis=1).tolist()

        axis[i].scatter(M, fc, color=colors, alpha=0.5)
        axis[i].axhline(y=0, color='black', linestyle='--', lw=0.5)

        axis[i].set_title(screen)

    for i in range(0, len(axis), 2):
        axis[i].set_ylabel("M")
    for ax in axis[-2:]:
        ax.set_xlabel("A")
    sns.despine(fig)
    fig.savefig(os.path.join(results_dir, "gRNA_counts.norm.{}.maplot.svg".format(prefix)), bbox_inches="tight")


def gRNA_rank(s1, s2, prefix=""):
    # Rank of gRNA change
    fig, axis = plt.subplots(3, 2, sharex=True, sharey=True, figsize=(8, 8))
    axis = axis.flatten()

    for i, screen in enumerate(s2.columns[::-1]):
        x = s1.join(s2)  # .fillna(0)
        x = x.iloc[np.random.permutation(len(x))]

        if "original" in prefix:
            if "TCR" in screen:
                x = x.ix[x.index[~x.index.str.contains("Wnt")]]
                fc = np.log2(1 + x[screen]) - np.log2(1 + x["plasmid_pool_TCR"])
            if "WNT" in screen:
                x = x.ix[x.index[~x.index.str.contains("Tcr")]]
                fc = np.log2(1 + x[screen]) - np.log2(1 + x["plasmid_pool_WNT"])
        elif "plasmid" not in prefix:
            if "TCR" in screen:
                x = x.ix[x.index[~x.index.str.contains("Wnt")]]
                fc = np.log2(1 + x[screen]) - np.log2(1 + x["gDNA_Jurkat"])
            if "_4_WNT" in screen:
                x = x.ix[x.index[~x.index.str.contains("Tcr")]]
                fc = np.log2(1 + x[screen]) - np.log2(1 + x["gDNA_HEKclone4"])
            if "_6_WNT" in screen:
                x = x.ix[x.index[~x.index.str.contains("Tcr")]]
                fc = np.log2(1 + x[screen]) - np.log2(1 + x["gDNA_HEKclone6"])
        else:
            fc = np.log2(1 + x[screen]) - np.log2(1 + x[0])

        fc.name = screen
        if i == 0:
            xx = pd.DataFrame(fc)
        else:
            xx = xx.join(fc, how="outer")

        colors = pd.DataFrame()
        colors[sns.color_palette("colorblind")[0]] = x.index.str.contains("Wnt")
        colors[sns.color_palette("colorblind")[1]] = x.index.str.contains("CTRL")
        colors[sns.color_palette("colorblind")[2]] = x.index.str.contains("Tcr")
        colors[sns.color_palette("colorblind")[3]] = x.index.str.contains("Ess")
        colors = colors.apply(lambda x: x[x].index.tolist()[0], axis=1).tolist()

        axis[i].scatter(fc.rank(ascending=False, method="first"), fc, color=colors, alpha=0.5)
        axis[i].axhline(y=0, color='black', linestyle='--', lw=0.5)

        axis[i].set_title(screen)

    for i in range(0, len(axis), 2):
        axis[i].set_ylabel("gRNA fold-change")
    for ax in axis[-2:]:
        ax.set_xlabel("gRNA rank")
    sns.despine(fig)
    fig.savefig(os.path.join(results_dir, "gRNA_counts.norm.{}.rank.svg".format(prefix)), bbox_inches="tight")

    xx.to_csv(os.path.join(results_dir, "gRNA_counts.norm.{}.rank.csv".format(prefix)), index=True)


def gRNA_rank_stimulus(xx, s2, prefix=""):
    # Difference between unstimulated/stimulated
    fig, axis = plt.subplots(1, 3, sharex=False, sharey=True, figsize=(12, 3))
    axis = iter(axis.flatten())

    for i, screen in enumerate(s2.columns[::-1]):
        x = s1.join(s2)  # .fillna(0)
        x = x.iloc[np.random.permutation(len(x))]

        if "original" in prefix:
            if "TCR" in screen:
                x = x.ix[x.index[~x.index.str.contains("Wnt")]]
                fc = np.log2(1 + x[screen]) - np.log2(1 + x["plasmid_pool_TCR"])
            if "WNT" in screen:
                x = x.ix[x.index[~x.index.str.contains("Tcr")]]
                fc = np.log2(1 + x[screen]) - np.log2(1 + x["plasmid_pool_WNT"])
        elif "plasmid" not in prefix:
            if "TCR" in screen:
                x = x.ix[x.index[~x.index.str.contains("Wnt")]]
                fc = np.log2(1 + x[screen]) - np.log2(1 + x["gDNA_Jurkat"])
            if "_4_WNT" in screen:
                x = x.ix[x.index[~x.index.str.contains("Tcr")]]
                fc = np.log2(1 + x[screen]) - np.log2(1 + x["gDNA_HEKclone4"])
            if "_6_WNT" in screen:
                x = x.ix[x.index[~x.index.str.contains("Tcr")]]
                fc = np.log2(1 + x[screen]) - np.log2(1 + x["gDNA_HEKclone6"])
        else:
            fc = np.log2(1 + x[screen]) - np.log2(1 + x[0])

        fc.name = screen
        if i == 0:
            xx = pd.DataFrame(fc)
        else:
            xx = xx.join(fc, how="outer")

    screens = s2.columns[::-1]
    for i in range(0, len(s2.columns), 2):
        ax = axis.next()
        fc = (xx[screens[i + 1]] - xx[screens[i]]).dropna()

        fc.name = screens[i + 1]
        if i == 0:
            ax.set_ylabel("gRNA fold-change (stimulated / unstimulated)")
            xxx = pd.DataFrame(fc)
        else:
            xxx = xxx.join(fc, how="outer")

        colors = pd.DataFrame()
        colors[sns.color_palette("colorblind")[0]] = fc.index.str.contains("Wnt")
        colors[sns.color_palette("colorblind")[1]] = fc.index.str.contains("CTRL")
        colors[sns.color_palette("colorblind")[2]] = fc.index.str.contains("Tcr")
        colors[sns.color_palette("colorblind")[3]] = fc.index.str.contains("Ess")
        colors = colors.apply(lambda j: j[j].index.tolist()[0], axis=1).tolist()

        ax.scatter(fc.rank(ascending=False, method="first"), fc, color=colors, alpha=0.5)
        ax.axhline(y=0, color='black', linestyle='--', lw=0.5)
        ax.set_title(re.sub("_stimulated", "", screens[i + 1]))
        ax.set_xlabel("gRNA rank (stimulated / unstimulated)")

    sns.despine(fig)
    fig.savefig(os.path.join(results_dir, "gRNA_counts.norm.{}.rank.diff_condition.svg".format(prefix)), bbox_inches="tight")

    xxx.columns = xxx.columns.str.extract("(.*)_stimulated")
    xxx.to_csv(os.path.join(results_dir, "gRNA_counts.norm.{}.rank.diff_condition.csv".format(prefix)), index=True)


root_dir = "/scratch/lab_bock/shared/projects/crop-seq"
results_dir = os.path.join(root_dir, "results")
sample_annotation = pd.read_csv(os.path.join(root_dir, "metadata/annotation.csv"))

# get guide annotation
guide_annotation = os.path.join(root_dir, "metadata/guide_annotation.csv")
guide_annotation = pd.read_csv(guide_annotation)


# get guide quantification pre screen
counts = ["plasmid_pool_ESS", "plasmid_pool_TCR", "plasmid_pool_WNT"]
pre_screen_counts = pd.DataFrame()
for count in counts:
    df = pd.read_csv(os.path.join("gRNA_counts", count + "_gRNA_count.tsv"), sep="\t")
    df["library"] = count
    pre_screen_counts = pre_screen_counts.append(df)
pre_screen_counts = pd.pivot_table(pre_screen_counts, index="gRNA_name", columns="library", values="count")
pre_screen_counts.to_csv(os.path.join(results_dir, "gRNA_counts.pre_screen.csv"), index=True)

# get guide quantification mid screen
counts = ["gDNA_HEKclone4", "gDNA_HEKclone6", "gDNA_Jurkat"]
mid_screen_counts = pd.DataFrame()
for count in counts:
    df = pd.read_csv(os.path.join("gRNA_counts", count + "_gRNA_count.tsv"), sep="\t")
    df["library"] = count
    mid_screen_counts = mid_screen_counts.append(df)
mid_screen_counts = pd.pivot_table(mid_screen_counts, index="gRNA_name", columns="library", values="count")
mid_screen_counts.to_csv(os.path.join(results_dir, "gRNA_counts.mid_screen.csv"), index=True)


# get guide quantification from CROP-seq
# merge output (reads in constructs and assignemnts) of each sample
reads_all = scores_all = assignment_all = pd.DataFrame()

for sample_name in sample_annotation[~sample_annotation["grna_library"].isnull()]["sample_name"].unique():
    reads = pd.read_csv(os.path.join(root_dir, "results_pipeline", sample_name, "quantification", "guide_cell_quantification.csv"))
    scores = pd.read_csv(os.path.join(root_dir, "results_pipeline", sample_name, "quantification", "guide_cell_scores.csv"), index_col=0).reset_index()
    assignment = pd.read_csv(os.path.join(root_dir, "results_pipeline", sample_name, "quantification", "guide_cell_assignment.csv"))

    reads["sample"] = scores["sample"] = assignment["sample"] = sample_name
    reads["experiment"] = scores["experiment"] = assignment["experiment"] = sample_name

    reads_all = reads_all.append(reads)
    scores_all = scores_all.append(scores)
    assignment_all = assignment_all.append(assignment)

reads_all.to_csv(os.path.join(results_dir, "guide_cell_quantification.all.csv"), index=False)
scores_all.to_csv(os.path.join(results_dir, "guide_cell_scores.all.csv"), index=False)
assignment_all.to_csv(os.path.join(results_dir, "guide_cell_assignment.all.csv"), index=False)

screen_counts = pd.pivot_table(assignment_all.groupby(["experiment", "assignment"]).apply(len).reset_index(), index="assignment", columns="experiment", fill_value=0)
screen_counts.columns = screen_counts.columns.droplevel(level=0)
screen_counts.to_csv(os.path.join(results_dir, "gRNA_counts.screen.csv"), index=True)


# Filter out non-existing gRNAs and opposite gRNA library.
# Use distribution of cells assigned with non-existing gRNAs
# to get 95th percentile of distribution as lower bound of sensitivity
# and further use it to filter out gRNAs with as many cells
pre_screen_counts = filter_gRNAs(pre_screen_counts, prefix="plasmid")
mid_screen_counts = filter_gRNAs(mid_screen_counts, prefix="mid_screen")
screen_counts = filter_gRNAs(screen_counts, prefix="screen")

# Normalize
pre_screen_counts = pre_screen_counts.apply(lambda x: (x / x.sum(skipna=True)) * 1e4, axis=0)
pre_screen_counts.to_csv(os.path.join(results_dir, "gRNA_counts.pre_screen.norm.csv"), index=True)

mid_screen_counts = mid_screen_counts.apply(lambda x: (x / x.sum(skipna=True)) * 1e4, axis=0)
mid_screen_counts.to_csv(os.path.join(results_dir, "gRNA_counts.mid_screen.norm.csv"), index=True)

screen_counts = screen_counts.apply(lambda x: (x / x.sum(skipna=True)) * 1e4, axis=0)
screen_counts.to_csv(os.path.join(results_dir, "gRNA_counts.screen.norm.csv"), index=True)


# for grna in mid_screen_counts.index[~mid_screen_counts.index.isin(screen_counts.index)]:
#     screen_counts.loc[grna, ] = 0
pre_sum = (pre_screen_counts.sum(axis=1) / pre_screen_counts.sum().sum()) * 1e4
pre_max = (pre_screen_counts.max(axis=1) / pre_screen_counts.sum().sum()) * 1e4

for s1, s1_ in [
        (pre_screen_counts, "original"),
        # (pd.DataFrame(pre_sum), "plasmid_sum"),
        # (pd.DataFrame(pre_max), "plasmid_max"),
        (mid_screen_counts, "mid_screen")]:
    for s2, s2_ in [(screen_counts, "crop_screen")]:
        gRNA_scatter(s1, s2, prefix="-".join([s1_, s2_]))
        gRNA_maplot(s1, s2, prefix="-".join([s1_, s2_]))
        gRNA_rank(s1, s2, prefix="-".join([s1_, s2_]))
        gRNA_rank_stimulus(s1, s2, prefix="-".join([s1_, s2_]))


# Get screen sensitivity
# Z-score
zez = list()

for screen, name in [
        (pre_screen_counts, "original"),
        (mid_screen_counts, "mid_screen"),
        (screen_counts, "crop_screen")]:

    fig, axis = plt.subplots(
        2 if name == "original" else 3, 2 if name == "crop_screen" else 1,
        sharex=False, sharey=False, figsize=(8 if name == "original" else 12, 12 if name == "crop_screen" else 8,))
    axis = axis.flatten()

    for i, col in enumerate(screen.columns[::-1]):
        z = screen_zscore(screen[col].dropna(), axis=axis[i])

        zez.append([name, col, z])

        axis[i].set_title(" ".join([name, col]))
        axis[i].set_xlabel("Number of cells assigned (log2)")
        axis[i].set_ylabel("Density")
        axis[i].legend()
    sns.despine(fig)
    fig.savefig(os.path.join(results_dir, "gRNA_counts.screen_sensitivity.{}.svg".format(name)), bbox_inches="tight")

zez = pd.DataFrame(zez)
zez.columns = ["timepoint", "sample", "z_score"]
zez["id"] = zez["timepoint"] + " " + zez["sample"]
zez["efficiency"] = 1 / -zez["z_score"]
zez.to_csv(os.path.join(results_dir, "gRNA_counts.screen_sensitivity.z_score.csv"), index=False)

# Barplot across experiments
zez = zez.sort_values(["efficiency"], ascending=False)
fig, axis = plt.subplots(1)
sns.barplot(zez["efficiency"], zez["id"], orient="h", ax=axis)
axis.set_title("Screen sensitivity")
axis.set_xlabel("Sensitivity (1 / Z score)")
sns.despine(fig)
fig.savefig(os.path.join(results_dir, "gRNA_counts.screen_sensitivity.barplot.svg"), bbox_inches="tight")


# plot replicates