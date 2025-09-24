// lib/screens/auth_screen.dart

import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:amplify_flutter/amplify_flutter.dart';
import 'package:amplify_auth_cognito/amplify_auth_cognito.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

// Import other screens needed for navigation
import 'otp_screen.dart'; // For navigation on sign up confirmation
import 'home_screen.dart'; // For navigation on sign in success
import 'forgot_password_screen.dart'; // Import the new screen
import 'profile_completion_screen.dart'; // Import the profile screen

// Renamed Class as requested
class AuthScreen extends StatefulWidget {
  final bool isSignUp;
  const AuthScreen({super.key, this.isSignUp = true});

  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

// Renamed Class as requested
class _AuthScreenState extends State<AuthScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController(); // For sign-up validation

  final _storage = const FlutterSecureStorage();
  late bool _isSignUp;
  bool _isLoading = false;
  final String _backendUrl = 'https://tzzexehfq1.execute-api.us-east-1.amazonaws.com/dev/'; // Adjust IP/port as needed for platform

  @override
  void initState() {
    super.initState();
    _isSignUp = widget.isSignUp;
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  // --- Main Submit Function (Handles both Sign Up and Sign In) ---
  Future<void> _submitForm() async {
    // Validate the form first
    if (!_formKey.currentState!.validate()) {
      return;
    }

    final email = _emailController.text.trim();
    final password = _passwordController.text.trim();

    if (mounted) setState(() { _isLoading = true; });

    try {
      if (_isSignUp) {
        // --- Sign Up Attempt ---
        await _handleSignUp(email, password);
      } else {
        // --- Sign In Attempt ---
        await _handleSignIn(email, password);
      }
    } on AuthException catch (e) {
      // Handle common Amplify Auth errors
      print("Amplify Auth Error: ${e.runtimeTypeName} - ${e.message}");
      // Use specific messages for common errors
      String friendlyMessage = e.message;
      if (e is UsernameExistsException) {
         friendlyMessage = 'An account with this email already exists. Try signing in.';
      } else if (e is InvalidPasswordException) {
         friendlyMessage = 'Password does not meet requirements. Check policy.';
      } else if (e is UserNotFoundException) {
         friendlyMessage = 'No account found with this email. Try signing up.';
      } 
      _showErrorSnackbar('Auth Error: $friendlyMessage');
    } catch (e) {
      // Handle other general errors (network from backend call, etc.)
      print("Error submitting form: $e");
      _showErrorSnackbar('An unexpected error occurred: $e');
    } finally {
       if (mounted) {
         setState(() { _isLoading = false; });
       }
    }
  } // End of _submitForm

  // --- Sign Up Logic ---
  Future<void> _handleSignUp(String email, String password) async {
    print("Attempting Sign Up for $email...");
    // Define user attributes (email is required by Cognito setup)
    final userAttributes = {AuthUserAttributeKey.email: email};

    final result = await Amplify.Auth.signUp(
      username: email, // Use email as the Cognito username
      password: password,
      options: SignUpOptions(userAttributes: userAttributes),
    );

    print("Sign Up result: ${result.nextStep.signUpStep}");

    // Check if confirmation code is needed
    if (result.nextStep.signUpStep == AuthSignUpStep.confirmSignUp) {
       if (mounted) {
         _showInfoSnackbar("Confirmation code sent to $email");
         // Navigate to OtpScreen, passing the email
         Navigator.push(
           context,
           MaterialPageRoute(
             builder: (context) => OtpScreen(email: email), // Navigate to OTP/Confirmation screen
           ),
         );
       }
    } else if (result.nextStep.signUpStep == AuthSignUpStep.done) {
       print("Sign up complete without confirmation step.");
       if (mounted) {
         setState(() { _isSignUp = false; }); // Switch to Sign In view
         _showInfoSnackbar('Sign up successful! Please sign in.');
       }
    }
  } // End of _handleSignUp

  // --- Sign In Logic ---
  Future<void> _handleSignIn(String email, String password) async {
    print("Attempting Sign In for $email...");

    // --- ADD THIS BLOCK FOR ROBUSTNESS ---
    // First, sign out any lingering session to ensure a clean login attempt.
    try {
      await Amplify.Auth.signOut();
      print("Signed out any existing session.");
    } on AuthException catch (e) {
      // This can happen if there was no user signed in. We can safely ignore it.
      print("No active session to sign out, proceeding with login: ${e.message}");
    }
    // --- END OF ADDITION ---

    final result = await Amplify.Auth.signIn(
      username: email,
      password: password,
    );

    print("Sign In result: step=${result.nextStep.signInStep}, isSignedIn=${result.isSignedIn}");

    if (result.isSignedIn) {
      print("Sign In Successful via Amplify!");
      // Now call the backend /auth/login endpoint to get backend session token
      await _callBackendLogin(); // Separate function for clarity

    } else {
       // Handle cases where sign in requires more steps
       print("Sign In requires further steps: ${result.nextStep.signInStep}");
       // Check if user exists but isn't confirmed (needs to verify email code)
       if (result.nextStep.signInStep == AuthSignInStep.confirmSignUp) {
          if (mounted) {
             _showErrorSnackbar('Account not confirmed. Please check your email for a code.');
             // Navigate to confirmation screen again
             Navigator.push(context, MaterialPageRoute(
                builder: (context) => OtpScreen(email: email), // Navigate to OTP/Confirmation screen
             ));
          }
       } else if (mounted) { // General fallback message for other steps
          // This could include MFA, selecting device, etc. if configured
          _showErrorSnackbar('Sign In requires additional steps: ${result.nextStep.signInStep}');
       }
    }
  } // End of _handleSignIn

  // --- Helper Function to Call Backend Login ---
  Future<void> _callBackendLogin() async {
     print("Getting Cognito ID token to send to backend...");
     try {
        var session = await Amplify.Auth.fetchAuthSession();
         if (session is! CognitoAuthSession) {
           throw Exception('Could not get Cognito session details.');
         }
        String? idToken = session.userPoolTokensResult.value.idToken.raw;

        if (idToken == null) {
           throw Exception("Couldn't get ID token from Cognito session.");
        }
        
        // --- ADD THIS LINE FOR DEBUGGING ---
        print('--- BEGIN ID TOKEN ---');
        print(idToken);
        print('--- END ID TOKEN ---');
        // ------------------------------------

        final url = Uri.parse('$_backendUrl/auth/login'); // Use defined backend URL
        print('Sending Cognito ID token to backend via Authorization header...');
        final response = await http.post(
          url,
          headers: {
            'Content-Type': 'application/json',
            'Authorization': idToken, // Send the ID token in the header
            'X-App-Type': 'PATIENT', // Add the required header for the patient app
          },
          // The body is now empty for this specific call
        );
        print('Backend Response Status: ${response.statusCode}');
        print('Backend Response Body: ${response.body}');

        if (!mounted) return;

        if (response.statusCode == 200) {
          final responseBody = jsonDecode(response.body);
          final String? apiToken = responseBody['api_token'];
          final Map<String, dynamic>? userProfile = responseBody['user_profile'];

          if (apiToken != null && userProfile != null) {
            await _storage.write(key: 'api_token', value: apiToken);
            await _storage.write(key: 'id_token', value: idToken); // persist ID token
            print('Final API token and user profile stored securely.');

            // --- NEW NAVIGATION LOGIC ---
            // Check for the patient-specific profile and its status.
            final Map<String, dynamic>? patientProfile = userProfile['patient_profile'];
            final String patientStatus = patientProfile?['status'] ?? 'PROFILE_INCOMPLETE';

            if (patientStatus == 'PROFILE_INCOMPLETE') {
              print('Patient profile is incomplete. Navigating to ProfileCompletionScreen.');
              Navigator.of(context).push(
                MaterialPageRoute(builder: (context) => const ProfileCompletionScreen()),
              );
            } else {
              print('Patient profile is complete. Navigating to HomeScreen.');
              Navigator.of(context).pushReplacement(
                MaterialPageRoute(builder: (context) => const HomeScreen()),
              );
            }
          } else {
             throw Exception("API token or user profile not found in backend response.");
          }
        } else {
           String errorMessage = "Backend login failed (${response.statusCode})";
           try { final errorBody = jsonDecode(response.body); errorMessage = "Backend error: ${errorBody['detail'] ?? response.body}"; } catch (_) {}
          throw Exception(errorMessage);
        }
     } catch(e) {
        // Re-throw to be caught by _submitForm's general handler
        print("Error during backend login call: $e");
        throw Exception('Error completing login with backend: $e');
     }
  } // End of _callBackendLogin

  // --- Helper functions for SnackBars ---
  void _showErrorSnackbar(String message) {
     if (mounted) {
       ScaffoldMessenger.of(context).removeCurrentSnackBar(); // Remove previous snackbar first
       ScaffoldMessenger.of(context).showSnackBar(
         SnackBar(content: Text(message), backgroundColor: Colors.redAccent));
     }
  }
   void _showInfoSnackbar(String message) {
     if (mounted) {
       ScaffoldMessenger.of(context).removeCurrentSnackBar();
       ScaffoldMessenger.of(context).showSnackBar(
         SnackBar(content: Text(message)));
     }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_isSignUp ? 'Create Account' : 'Sign In'),
        automaticallyImplyLeading: false,
      ),
      body: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Form(
          key: _formKey,
          child: ListView(
            children: <Widget>[
              TextFormField(
                controller: _emailController,
                keyboardType: TextInputType.emailAddress,
                autocorrect: false,
                decoration: const InputDecoration(labelText: 'Email Address', border: OutlineInputBorder()),
                validator: (value) {
                  if (value == null || value.trim().isEmpty || !value.contains('@')) { // Basic validation
                    return 'Please enter a valid email address';
                  } return null;
                },
              ),
              const SizedBox(height: 20),
              TextFormField(
                controller: _passwordController,
                obscureText: true,
                autocorrect: false,
                decoration: const InputDecoration(labelText: 'Password', border: OutlineInputBorder()),
                 validator: (value) {
                  if (value == null || value.isEmpty) { return 'Please enter a password'; }
                  // Example: Align with a common Cognito default policy (can be customized)
                  // if (value.length < 8) { return 'Password must be at least 8 characters';}
                  // bool hasUppercase = value.contains(RegExp(r'[A-Z]'));
                  // bool hasLowercase = value.contains(RegExp(r'[a-z]'));
                  // bool hasDigits = value.contains(RegExp(r'[0-9]'));
                  // if (!hasUppercase || !hasLowercase || !hasDigits) {
                  //   return 'Password needs uppercase, lowercase, and digits.';
                  // }
                  return null; // Keep simple validation for now
                },
              ),
              const SizedBox(height: 20),
              // Only show Confirm Password in Sign Up mode
              if (_isSignUp)
                TextFormField(
                  controller: _confirmPasswordController,
                  obscureText: true,
                  autocorrect: false,
                  decoration: const InputDecoration(labelText: 'Confirm Password', border: OutlineInputBorder()),
                   validator: (value) {
                    if (_isSignUp && (value == null || value.isEmpty)) { return 'Please confirm your password';}
                    if (_isSignUp && value != _passwordController.text) { return 'Passwords do not match';}
                    return null;
                  },
                ),
              if (_isSignUp) const SizedBox(height: 30),

              _isLoading
                ? const Center(child: CircularProgressIndicator())
                : ElevatedButton(
                    onPressed: _submitForm, // Calls the combined logic
                    style: ElevatedButton.styleFrom(
                      minimumSize: const Size(double.infinity, 50),
                      textStyle: const TextStyle(fontSize: 18)
                    ),
                    child: Text(_isSignUp ? 'Sign Up' : 'Sign In'),
                  ),
              const SizedBox(height: 10),
              // --- ADD FORGOT PASSWORD BUTTON ---
              if (!_isSignUp)
                TextButton(
                  onPressed: () {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (context) => const ForgotPasswordScreen(),
                      ),
                    );
                  },
                  child: const Text('Forgot Password?'),
                ),
              // --- END OF ADDITION ---
              const SizedBox(height: 10),
              // Toggle Button
              TextButton(
                onPressed: _isLoading ? null : () { setState(() { _isSignUp = !_isSignUp; }); },
                child: Text(_isSignUp ? 'Already have an account? Sign In' : 'Don\'t have an account? Sign Up'),
              ),
            ],
          ),
        ),
      ),
    );
  }
} // End of _AuthScreenState class