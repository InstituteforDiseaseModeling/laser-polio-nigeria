suppressPackageStartupMessages({
    library(tidyverse)
    library(jsonlite)
    library(dplyr)
    library(geosphere)
    library(rhdf5)
})
options(max.print = 1000)

# ------------------------------
# Load & curate data
# ------------------------------

# Load the historic SIA schedule
historic_sias <- read_csv("data/sia_historic_schedule.csv") %>%
    mutate(
        date = as.Date(date),
        year = year(date)
    )

# Filter to Nigeria
historic_sias <- historic_sias %>%
    filter(str_detect(dot_name, "NIGERIA")) %>%
    filter(year >= 2017) %>%
    filter(vaccinetype %in% c("mOPV2", "topv", "nOPV2"))

# Add lat long to the historic_sias dataframe
node_lookup <- fromJSON("data/node_lookup.json")
node_df <- bind_rows(node_lookup)
historic_sias <- historic_sias %>%
    left_join(node_df, by = c("dot_name" = "dot_name"))

# Load the historic cases data
cases <- h5read("data/epi_africa_20250421.h5", "/epi", compoundAsDataFrame = FALSE)


df <- h5read("data/epi_africa_20250421.h5", "/epi", compoundAsDataFrame = FALSE)
df <- as.data.frame(df)
h5closeAll()


library(reticulate)
library(dplyr)
pd <- import("pandas")
df <- pd$read_hdf("data/epi_africa_20250421.h5", key = "epi")
df <- as.data.frame(df) |>
    filter(str_detect(dot_name, "NIGERIA")) |>
    mutate(year = year(month_start)) |>
    filter(year >= 2017)


# ------------------------------
# Summarize the number of SIAs per year
# ------------------------------

# Summarize the historic SIA schedule
sias_per_year <- historic_sias %>%
    group_by(year) %>%
    summarize(n_sias = n_distinct(date))
print(sias_per_year)

summary(sias_per_year$n_sias)


ggplot(sias_per_year, aes(x = year, y = n_sias, label = n_sias)) +
    geom_line() +
    geom_point() +
    geom_text(vjust = -0.5) +
    labs(
        title = "Number of SIAs per Year",
        x = "Year",
        y = "Number of SIAs"
    )


# ------------------------------
# Average amount of time between SIAs
# ------------------------------

avg_gaps <- historic_sias %>%
    arrange(dot_name, date) %>% # order within each district
    group_by(dot_name) %>%
    mutate(
        gap_days = as.numeric(date - lag(date)) # days between this and previous event
    )
summary(avg_gaps$gap_days)

ggplot(avg_gaps %>% filter(gap_days < 60), aes(x = gap_days)) +
    geom_histogram() +
    labs(
        title = "Distribution of Time Between SIAs",
        x = "Time Between SIAs (days)",
        y = "Count"
    )


ggplot(avg_gaps %>% filter(gap_days > 75), aes(x = gap_days)) +
    geom_histogram() +
    labs(
        title = "Distribution of Time Between SIAs",
        x = "Time Between SIAs (days)",
        y = "Count"
    )
# %>%
# summarise(
#     n_events        = n(),
#     n_intervals     = sum(!is.na(gap_days)),
#     mean_gap_days   = mean(gap_days, na.rm = TRUE),
#     median_gap_days = median(gap_days, na.rm = TRUE)
# )


# ------------------------------
# Summarize the size of SIAs
# ------------------------------

# Average number of province per SIA
avg_provinces_per_sias <- historic_sias %>%
    group_by(date) %>%
    summarize(n_provinces = n_distinct(adm1))
print(avg_provinces_per_sias)
summary(avg_provinces_per_sias$n_provinces)
ggplot(avg_provinces_per_sias, aes(x = n_provinces)) +
    geom_histogram() +
    labs(
        title = "Number of Provinces per SIA",
        x = "Number of Provinces",
        y = "Count"
    )


# Average number of nodes per SIA
avg_nodes_per_sias <- historic_sias %>%
    group_by(date) %>%
    summarize(n_nodes = n())
print(avg_nodes_per_sias)

# Overall average
summary(avg_nodes_per_sias$n_nodes)

avg_nodes_per_sias_per_year <- historic_sias %>%
    group_by(year, date) %>%
    group_by(year) %>%
    summarize(n_nodes = n())
print(avg_nodes_per_sias_per_year)

ggplot(avg_nodes_per_sias_per_year, aes(x = year, y = n_nodes, label = n_nodes)) +
    geom_line() +
    geom_point() +
    geom_text(vjust = -0.5) +
    labs(
        title = "Number of Nodes per SIA",
        x = "Date",
        y = "Number of Nodes"
    )

# Average geographic width of SIAs

# Function to calculate pairwise distances for a group
calc_pairwise_distances <- function(df) {
    n <- nrow(df)
    if (n < 2) {
        return(data.frame(
            dot_name_1 = character(),
            dot_name_2 = character(),
            distance_km = numeric()
        ))
    }

    # Create all pairs
    pairs <- expand.grid(i = 1:n, j = 1:n) %>%
        filter(i < j)

    # Calculate distances
    results <- data.frame(
        dot_name_1 = df$dot_name[pairs$i],
        dot_name_2 = df$dot_name[pairs$j],
        distance_km = distHaversine(
            cbind(df$lon[pairs$i], df$lat[pairs$i]),
            cbind(df$lon[pairs$j], df$lat[pairs$j])
        ) / 1000
    )

    return(results)
}


# Apply to each date
distance_summary <- historic_sias %>%
    group_by(date) %>%
    group_modify(~ calc_pairwise_distances(.x)) %>%
    ungroup() %>%
    group_by(date) %>%
    summarise(
        n_locations = n_distinct(c(dot_name_1, dot_name_2)),
        n_pairs = n(),
        mean_dist_km = mean(distance_km),
        max_dist_km = max(distance_km),
        min_dist_km = min(distance_km)
    )

hist(distance_summary$max_dist_km)
summary(distance_summary$max_dist_km)




# Number of cases in previous 6 months
# Number in last month
# Number since last SIA
# At provincial level:
# - Number of annual SIAs
# - Number of provinces per SIA
# - Numer of cases in 6 months prior to SIA
# - Numer of cases in last month prior to SIA
# - Numer of cases since last SIA


# ------------------------------
# Summarize the number of cases in previous 6 months
# ------------------------------

# Number of cases in previous 6 months
cases_in_previous_6_months <- historic_sias %>%
    group_by(date) %>%
    summarize(n_cases = n())
print(cases_in_previous_6_months)
summary(cases_in_previous_6_months$n_cases)
