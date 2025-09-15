import 'package:flutter/material.dart';

class AppTheme {
  static final ThemeData lightTheme = ThemeData(
    // 1. Set the color scheme
    colorScheme: ColorScheme.fromSeed(
      seedColor: const Color(0xFF212121), // Charcoal as the primary seed color
      primary: const Color(0xFF212121),   // Charcoal for primary elements like buttons
      onPrimary: Colors.white,            // Text color on primary elements (e.g., on buttons)
      secondary: const Color(0xFF5A5A5A), // A slightly lighter grey for secondary elements
      onSecondary: Colors.white,          // Text color on secondary elements
      background: Colors.white,           // The main app background color
      onBackground: const Color(0xFF212121), // Text color on the background
      surface: Colors.white,              // The color of card backgrounds, dialogs, etc.
      onSurface: const Color(0xFF212121),  // Text color on surfaces
      error: Colors.redAccent,
      onError: Colors.white,
    ),

    // 2. Set the AppBar theme
    appBarTheme: const AppBarTheme(
      backgroundColor: Colors.white,      // White app bar
      foregroundColor: Color(0xFF212121), // Charcoal color for title and icons
      elevation: 1,                       // A subtle shadow for depth
      iconTheme: IconThemeData(color: Color(0xFF212121)),
    ),

    // 3. Set the ElevatedButton theme
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: const Color(0xFF212121), // Charcoal button background
        foregroundColor: Colors.white,            // White button text
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      ),
    ),

    // Add OutlinedButton theme
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: const Color(0xFF212121), // Charcoal text and icon color
        side: const BorderSide(color: Color(0xFF212121)), // Charcoal border
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      ),
    ),

    // 4. Set the text theme (optional, can be refined later)
    textTheme: const TextTheme(
      displayLarge: TextStyle(color: Color(0xFF212121)),
      displayMedium: TextStyle(color: Color(0xFF212121)),
      bodyMedium: TextStyle(color: Color(0xFF212121)),
      titleLarge: TextStyle(color: Color(0xFF212121), fontWeight: FontWeight.bold),
    ),
    
    // 5. Set the input decoration theme for text fields
    inputDecorationTheme: InputDecorationTheme(
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: Colors.grey),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: Color(0xFF212121), width: 2),
      ),
      labelStyle: const TextStyle(color: Color(0xFF212121)),
    ),
    
    // Use Material 3 design
    useMaterial3: true,
  );
}
