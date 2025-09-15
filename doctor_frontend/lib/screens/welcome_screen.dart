import 'package:flutter/material.dart';
import 'auth_screen.dart';

class WelcomeScreen extends StatelessWidget {
  const WelcomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Spacer(flex: 2),
              // Icon Placeholder
              const Icon(
                Icons.medical_services_outlined, // Placeholder icon
                size: 64,
                color: Color(0xFF212121),
              ),
              const SizedBox(height: 24),
              // App Name
              const Text(
                'Aria',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 48,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'for Doctors',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 18,
                  color: Theme.of(context).colorScheme.secondary,
                ),
              ),
              const Spacer(flex: 3),
              // Sign Up Button
              ElevatedButton(
                onPressed: () {
                  Navigator.of(context).push(MaterialPageRoute(
                    builder: (context) => const AuthScreen(isSignUp: true),
                  ));
                },
                child: const Text('Sign Up'),
              ),
              const SizedBox(height: 16),
              // Sign In Button
              OutlinedButton(
                onPressed: () {
                  Navigator.of(context).push(MaterialPageRoute(
                    builder: (context) => const AuthScreen(isSignUp: false),
                  ));
                },
                child: const Text('Sign In'),
              ),
              const Spacer(flex: 1),
              // Tagline
              const Text(
                'Secure • Private • Always Available',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: Colors.grey,
                  fontSize: 12,
                ),
              ),
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }
}
