# ================================================================
#  TN LOAD FORECASTING — STREAMLIT-INTEGRATED ROLLING FORECASTER
#
#  This is a simplified version optimized for Streamlit integration.
#  Use this as a utility module in your Streamlit app.
#
#  USAGE in Streamlit:
#  -------------------
#  import streamlit_rolling_forecaster as rf
#  
#  if st.button("Run Rolling Forecast"):
#      df_results = rf.run_rolling_forecast(
#          hist_csv="Data__2020-2026_3rd_month_.csv",
#          actual_csv="Apr-Jun_2026.csv",
#          forecast_months=[7, 8, 9],
#          progress_bar=st.progress
#      )
#      st.dataframe(df_results)
#
# ================================================================

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import pickle
import json

# Deep Learning
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau

from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_percentage_error

import warnings
warnings.filterwarnings('ignore')
tf.get_logger().setLevel('ERROR')


# ═════════════════════════════════════════════════════════════════
#  CONFIG
# ═════════════════════════════════════════════════════════════════

class RollingForecastConfig:
    """Configuration for rolling forecasting."""
    
    LOOKBACK = 168  # 1 week of hourly data
    FORECAST_H = 24  # 24 hours ahead
    
    # LSTM
    LSTM_U1 = 128
    LSTM_U2 = 64
    DENSE_U = 32
    DROPOUT = 0.3
    
    # Training
    EPOCHS = 150
    BATCH_SIZE = 64
    PATIENCE = 20
    LR = 0.001
    VAL_SPLIT = 0.1
    
    # Forecast
    DEFAULT_FORECAST_MONTHS = [7, 8, 9]
    
    # TN Holidays
    TN_HOLIDAYS = {
        pd.Timestamp(2020, 1, 26), pd.Timestamp(2020, 3, 25),
        pd.Timestamp(2020, 4, 2), pd.Timestamp(2020, 4, 10),
        pd.Timestamp(2020, 10, 2), pd.Timestamp(2020, 10, 25),
        pd.Timestamp(2020, 11, 14), pd.Timestamp(2020, 12, 25),
    }


# ═════════════════════════════════════════════════════════════════
#  DATA PREPARATION
# ═════════════════════════════════════════════════════════════════

class DataPreprocessor:
    """Handles data loading and feature engineering."""
    
    REQUIRED_COLS = [
        'Datetime', 'load', 'temperature', 'humidity', 'rain ',
        'wind 10', 'wind 100', 'radiation ', 'cloud_cover ',
        'year', 'month', 'day', 'hour', 'day_of_week', 'day_of_year',
        'is_summer', 'is_monsoon', 'is_holiday',
        'load_lag_24', 'load_lag_48', 'load_lag_168',
        'load_roll_mean_24', 'load_roll_mean_168', 'load_roll_std_24'
    ]
    
    @staticmethod
    def load_and_merge(hist_path, actual_path, status_func=None):
        """Load and merge historical + new actual data."""
        
        if status_func:
            status_func("📂 Loading historical data...")
        
        df_hist = pd.read_csv(hist_path, parse_dates=['Datetime'])
        
        if status_func:
            status_func(f"📂 Loading actual data ({actual_path})...")
        
        df_actual = pd.read_csv(actual_path, parse_dates=['Datetime'])
        
        # Combine
        df = pd.concat([df_hist, df_actual], ignore_index=True)
        df = df.sort_values('Datetime').drop_duplicates(
            subset=['Datetime'], keep='last'
        ).reset_index(drop=True)
        
        return df
    
    @staticmethod
    def add_features(df):
        """Add temporal and weather features."""
        
        df = df.sort_values('Datetime').reset_index(drop=True)
        
        # Temporal
        df['year'] = df['Datetime'].dt.year
        df['month'] = df['Datetime'].dt.month
        df['day'] = df['Datetime'].dt.day
        df['hour'] = df['Datetime'].dt.hour
        df['day_of_week'] = df['Datetime'].dt.dayofweek
        df['day_of_year'] = df['Datetime'].dt.dayofyear
        df['week_of_year'] = df['Datetime'].dt.isocalendar().week
        
        # Season
        df['is_summer'] = (df['month'].isin([3, 4, 5, 6])).astype(int)
        df['is_monsoon'] = (df['month'].isin([10, 11, 12])).astype(int)
        df['is_peak_hour'] = (df['hour'].isin([15, 16, 17, 18])).astype(int)
        
        # Holiday
        df['is_holiday'] = df['Datetime'].apply(
            lambda x: int(x.normalize() in RollingForecastConfig.TN_HOLIDAYS)
        )
        
        # Clean weather columns
        weather_cols = ['temperature', 'humidity', 'rain ', 'wind 10', 'wind 100',
                       'radiation ', 'cloud_cover ']
        for col in weather_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                df[col] = df[col].fillna(df[col].median())
        
        return df
    
    @staticmethod
    def add_lags(df):
        """Add lagged and rolling features."""
        
        df = df.sort_values('Datetime').reset_index(drop=True)
        
        df['load_lag_24'] = df['load'].shift(24)
        df['load_lag_48'] = df['load'].shift(48)
        df['load_lag_168'] = df['load'].shift(168)
        
        df['load_roll_mean_24'] = df['load'].shift(1).rolling(24, min_periods=1).mean()
        df['load_roll_mean_168'] = df['load'].shift(1).rolling(168, min_periods=1).mean()
        df['load_roll_std_24'] = df['load'].shift(1).rolling(24, min_periods=1).std()
        
        df = df.ffill().bfill()
        
        return df
    
    @staticmethod
    def preprocess(hist_path, actual_path, status_func=None):
        """Full preprocessing pipeline."""
        
        df = DataPreprocessor.load_and_merge(hist_path, actual_path, status_func)
        
        if status_func:
            status_func("🔧 Adding features...")
        
        df = DataPreprocessor.add_features(df)
        df = DataPreprocessor.add_lags(df)
        
        # Keep only required columns
        cols_to_keep = [c for c in DataPreprocessor.REQUIRED_COLS if c in df.columns]
        df = df[cols_to_keep].dropna()
        
        return df, cols_to_keep


# ═════════════════════════════════════════════════════════════════
#  LSTM MODEL
# ═════════════════════════════════════════════════════════════════

class LSTMForecaster:
    """LSTM-based forecasting model."""
    
    def __init__(self, config=None):
        self.config = config or RollingForecastConfig()
        self.model = None
        self.feature_scaler = None
        self.target_scaler = None
    
    def build_and_train(self, df_train, feature_cols, status_func=None):
        """Build and train LSTM."""
        
        if status_func:
            status_func("🏗️ Building LSTM model...")
        
        cfg = self.config
        
        # Scalers
        self.feature_scaler = MinMaxScaler(feature_range=(0, 1))
        self.target_scaler = MinMaxScaler(feature_range=(0, 1))
        
        X_raw = df_train[feature_cols].values
        y_raw = df_train[['load']].values
        
        X_scaled = self.feature_scaler.fit_transform(X_raw)
        y_scaled = self.target_scaler.fit_transform(y_raw)
        
        # Sequences
        X, y = [], []
        target_idx = feature_cols.index('load')
        
        for i in range(cfg.LOOKBACK, len(X_scaled) - cfg.FORECAST_H + 1):
            X.append(X_scaled[i - cfg.LOOKBACK:i, :])
            y.append(y_scaled[i:i + cfg.FORECAST_H, 0])
        
        X = np.array(X)
        y = np.array(y)
        
        split_idx = int(len(X) * (1 - cfg.VAL_SPLIT))
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]
        
        # Model
        self.model = Sequential([
            LSTM(cfg.LSTM_U1, return_sequences=True,
                 input_shape=(cfg.LOOKBACK, len(feature_cols))),
            Dropout(cfg.DROPOUT),
            BatchNormalization(),
            LSTM(cfg.LSTM_U2, return_sequences=False),
            Dropout(cfg.DROPOUT),
            BatchNormalization(),
            Dense(cfg.DENSE_U, activation='relu'),
            Dropout(cfg.DROPOUT / 2),
            Dense(cfg.FORECAST_H, activation='linear'),
        ])
        
        self.model.compile(
            optimizer=Adam(learning_rate=cfg.LR),
            loss='huber',
            metrics=['mae']
        )
        
        if status_func:
            status_func(f"🚀 Training ({cfg.EPOCHS} epochs)...")
        
        self.model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=cfg.EPOCHS,
            batch_size=cfg.BATCH_SIZE,
            callbacks=[
                EarlyStopping(
                    monitor='val_loss',
                    patience=cfg.PATIENCE,
                    restore_best_weights=True,
                    verbose=0
                ),
                ReduceLROnPlateau(
                    monitor='val_loss',
                    factor=0.5,
                    patience=4,
                    min_lr=1e-6,
                    verbose=0
                ),
            ],
            verbose=0
        )
    
    def predict_day(self, df_window, feature_cols):
        """Predict 24 hours ahead."""
        
        window_data = df_window.iloc[-self.config.LOOKBACK:][feature_cols].values
        window_scaled = self.feature_scaler.transform(window_data)
        X_pred = window_scaled.reshape(1, self.config.LOOKBACK, len(feature_cols))
        
        y_pred_scaled = self.model.predict(X_pred, verbose=0)[0]
        y_pred = self.target_scaler.inverse_transform(
            y_pred_scaled.reshape(-1, 1)
        ).flatten()
        
        return y_pred


# ═════════════════════════════════════════════════════════════════
#  ROLLING FORECAST ENGINE
# ═════════════════════════════════════════════════════════════════

class RollingForecastEngine:
    """Orchestrates the rolling forecast process."""
    
    def __init__(self, config=None):
        self.config = config or RollingForecastConfig()
        self.forecaster = LSTMForecaster(config)
    
    def run(self, hist_path, actual_path, forecast_months=None, status_func=None):
        """
        Run complete rolling forecast pipeline.
        
        Args:
            hist_path: Path to historical data CSV
            actual_path: Path to new actual data CSV
            forecast_months: List of months to forecast (default: [7,8,9])
            status_func: Callback for progress updates
        
        Returns:
            DataFrame with forecasts
        """
        
        if forecast_months is None:
            forecast_months = self.config.DEFAULT_FORECAST_MONTHS
        
        # Preprocess
        if status_func:
            status_func("📊 Preprocessing data...")
        
        df_combined, feature_cols = DataPreprocessor.preprocess(
            hist_path, actual_path, status_func
        )
        
        # Split
        df_train = df_combined[~df_combined['month'].isin(forecast_months)].copy()
        df_actual = df_combined[df_combined['month'].isin(forecast_months)].copy()
        
        # Train
        self.forecaster.build_and_train(df_train, feature_cols, status_func)
        
        # Forecast
        if status_func:
            status_func("🔮 Running rolling forecast...")
        
        df_forecast = self._rolling_forecast(
            df_combined, df_actual, feature_cols, forecast_months, status_func
        )
        
        return df_forecast
    
    def _rolling_forecast(self, df_combined, df_actual, feature_cols, 
                         forecast_months, status_func):
        """Rolling forecast logic."""
        
        last_actual_date = df_actual['Datetime'].max()
        last_year = last_actual_date.year
        
        results = []
        
        # Generate all forecast dates
        forecast_dates = []
        for month in forecast_months:
            if month == 12:
                next_month_first = pd.Timestamp(year=last_year + 1, month=1, day=1)
            else:
                next_month_first = pd.Timestamp(year=last_year, month=month + 1, day=1)
            
            last_day = (next_month_first - timedelta(days=1)).day
            for day in range(1, last_day + 1):
                forecast_dates.append(pd.Timestamp(year=last_year, month=month, day=day))
        
        # Rolling forecast
        df_train_extended = df_combined[df_combined['Datetime'] <= last_actual_date].copy()
        
        for idx, forecast_date in enumerate(forecast_dates, 1):
            if status_func and idx % 10 == 0:
                status_func(f"📅 Day {idx}/{len(forecast_dates)}...")
            
            # Get window for prediction
            window_start = forecast_date - timedelta(days=self.config.LOOKBACK)
            df_window = df_train_extended[
                (df_train_extended['Datetime'] >= window_start) &
                (df_train_extended['Datetime'] < forecast_date)
            ]
            
            if len(df_window) < self.config.LOOKBACK:
                continue
            
            # Predict
            pred_hourly = self.forecaster.predict_day(df_window, feature_cols)
            pred_avg = np.mean(pred_hourly)
            pred_peak = np.max(pred_hourly)
            
            # Store result
            result_row = {
                'date': forecast_date.strftime('%Y-%m-%d'),
                'month': forecast_date.month,
                'day': forecast_date.day,
                'day_of_week': forecast_date.dayofweek,
                'predicted_avg': round(pred_avg, 1),
                'predicted_peak': round(pred_peak, 1),
            }
            
            # Hourly
            for h, load in enumerate(pred_hourly):
                result_row[f'pred_h{h:02d}'] = round(load, 1)
            
            results.append(result_row)
            
            # Add synthetic row to training data
            synthetic_row = {
                'Datetime': forecast_date,
                'load': pred_avg,
                'temperature': df_train_extended.iloc[-1]['temperature'],
                'humidity': df_train_extended.iloc[-1]['humidity'],
                'rain ': 0,
                'wind 10': df_train_extended.iloc[-1]['wind 10'],
                'wind 100': df_train_extended.iloc[-1]['wind 100'],
                'radiation ': 0,
                'cloud_cover ': df_train_extended.iloc[-1]['cloud_cover '],
                'year': forecast_date.year,
                'month': forecast_date.month,
                'day': forecast_date.day,
                'hour': 12,
                'day_of_week': forecast_date.dayofweek,
                'day_of_year': forecast_date.dayofyear,
                'week_of_year': forecast_date.isocalendar().week,
                'is_summer': int(forecast_date.month in [3, 4, 5, 6]),
                'is_monsoon': int(forecast_date.month in [10, 11, 12]),
                'is_peak_hour': 1,
                'is_holiday': int(forecast_date.normalize() in RollingForecastConfig.TN_HOLIDAYS),
                'load_lag_24': df_train_extended.iloc[-24]['load'] if len(df_train_extended) > 24 else pred_avg,
                'load_lag_48': df_train_extended.iloc[-48]['load'] if len(df_train_extended) > 48 else pred_avg,
                'load_lag_168': df_train_extended.iloc[-168]['load'] if len(df_train_extended) > 168 else pred_avg,
                'load_roll_mean_24': df_train_extended.iloc[-24:]['load'].mean(),
                'load_roll_mean_168': df_train_extended.iloc[-168:]['load'].mean(),
                'load_roll_std_24': df_train_extended.iloc[-24:]['load'].std(),
            }
            
            df_new = pd.DataFrame([synthetic_row])
            df_train_extended = pd.concat([df_train_extended, df_new], 
                                         ignore_index=True)
        
        return pd.DataFrame(results)


# ═════════════════════════════════════════════════════════════════
#  PUBLIC API
# ═════════════════════════════════════════════════════════════════

def run_rolling_forecast(hist_csv, actual_csv, forecast_months=None, 
                        status_func=None, config=None):
    """
    Simple API to run rolling forecast.
    
    Args:
        hist_csv: Path to historical data
        actual_csv: Path to new actual data
        forecast_months: Months to forecast (default: [7,8,9])
        status_func: Progress callback
        config: RollingForecastConfig instance
    
    Returns:
        DataFrame with forecasts
    
    Example:
        >>> df = run_rolling_forecast(
        ...     "historical.csv",
        ...     "actual_2026.csv",
        ...     forecast_months=[7, 8, 9]
        ... )
        >>> df.to_csv("forecast_results.csv", index=False)
    """
    
    engine = RollingForecastEngine(config)
    return engine.run(hist_csv, actual_csv, forecast_months, status_func)
