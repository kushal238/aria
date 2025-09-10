// lib/screens/otp_screen.dart

import 'package:flutter/material.dart';
import 'package:amplify_flutter/amplify_flutter.dart'; // Amplify Core
import 'package:amplify_auth_cognito/amplify_auth_cognito.dart'; // Amplify Auth Cognito
import 'package:pinput/pinput.dart'; // Keep pinput

// Keep class name OtpScreen
class OtpScreen extends StatefulWidget {
  // Change constructor to accept email instead of verificationId
  final String email;
  const OtpScreen({super.key, required this.email});

  @override
  State<OtpScreen> createState() => _OtpScreenState();
}

// Keep class name _OtpScreenState
class _OtpScreenState extends State<OtpScreen> {
  final TextEditingController _otpController = TextEditingController();
  final FocusNode _otpFocusNode = FocusNode();
  bool _isLoading = false;
  // Remove _auth, _storage - not needed here anymore

  @override
  void dispose() {
    _otpController.dispose();
    _otpFocusNode.dispose();
    super.dispose();
  }

  // --- Function to confirm the sign up code ---
  Future<void> _confirmSignUp() async {
    final String confirmationCode = _otpController.text.trim();

    // Basic validation
    if (confirmationCode.length != 6) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Please enter the complete 6-digit code.')));
      return;
    }

    if (mounted) setState(() { _isLoading = true; });

    try {
      print("Attempting Amplify.Auth.confirmSignUp for ${widget.email} with code $confirmationCode");

      // Call Amplify to confirm the sign up using the email and code
      final SignUpResult result = await Amplify.Auth.confirmSignUp(
        username: widget.email, // Use the email passed to this screen
        confirmationCode: confirmationCode,
      );

      print("Amplify confirmSignUp result: isSignUpComplete=${result.isSignUpComplete}, nextStep=${result.nextStep.signUpStep}");

      // Check if sign up confirmation is complete
      if (result.isSignUpComplete) {
        print("Sign Up Confirmation Successful!");
         if (mounted) {
           // Show success message
           ScaffoldMessenger.of(context).showSnackBar(
             const SnackBar(content: Text('Account confirmed successfully! Please Sign In.')));
           // Navigate back to the previous screen (AuthScreen)
           Navigator.of(context).pop(); // Pop this screen off the stack
         }
         return; // Exit function
      } else {
         // This case should ideally not happen if confirmSignUp is the expected step
         print("Amplify confirmSignUp requires further steps: ${result.nextStep.signUpStep}");
         throw Exception("Unexpected step after code confirmation: ${result.nextStep.signUpStep}");
      }

    } on AuthException catch (e) {
      // Handle Amplify specific errors like CodeMismatchException, ExpiredCodeException, UserNotFoundException etc.
      print("Amplify Confirm SignUp Failed: ${e.runtimeTypeName} - ${e.message}");
       if (mounted) {
         ScaffoldMessenger.of(context).showSnackBar(
             SnackBar(content: Text('Confirmation Error: ${e.message}')));
       }
    } catch (e) {
      // Handle other general errors
      print("An error occurred during code confirmation: $e");
       if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
             SnackBar(content: Text('An unexpected error occurred: $e')));
       }
    } finally {
       if (mounted) {
         setState(() { _isLoading = false; });
       }
    }
  } // End of _confirmSignUp

  // Optional: Add Resend Code Functionality
  Future<void> _resendConfirmationCode() async {
     if (mounted) setState(() { _isLoading = true; });
     try {
        print("Attempting to resend confirmation code for ${widget.email}");
        await Amplify.Auth.resendSignUpCode(username: widget.email);
        print("Resend code request successful.");
         if (mounted) {
             ScaffoldMessenger.of(context).showSnackBar(
               const SnackBar(content: Text('Confirmation code resent successfully.')));
         }
     } on AuthException catch (e) {
         print("Error resending code: ${e.message}");
          if (mounted) {
             ScaffoldMessenger.of(context).showSnackBar(
               SnackBar(content: Text('Error resending code: ${e.message}')));
          }
     } catch (e) {
         print("Unexpected error resending code: $e");
          if (mounted) {
             ScaffoldMessenger.of(context).showSnackBar(
               SnackBar(content: Text('An unexpected error occurred: $e')));
          }
     } finally {
         if (mounted) setState(() { _isLoading = false; });
     }
  }


  @override
  Widget build(BuildContext context) {
    // Define pinput theme - Keep as is
    final defaultPinTheme = PinTheme(
      width: 56,
      height: 60,
      textStyle: const TextStyle(fontSize: 22, color: Colors.black),
      decoration: BoxDecoration(
        color: Colors.grey.shade200,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.transparent),
      ),
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Verify Email Code'), // Update title
      ),
      body: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text( // Update prompt text
                'Enter the 6-digit code sent to ${widget.email}.', // Show email
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 16),
              ),
              const SizedBox(height: 40),
              Pinput( // Keep Pinput UI
                length: 6,
                controller: _otpController,
                focusNode: _otpFocusNode,
                defaultPinTheme: defaultPinTheme,
                focusedPinTheme: defaultPinTheme.copyWith(
                  decoration: defaultPinTheme.decoration!.copyWith(
                    border: Border.all(color: Theme.of(context).primaryColor),
                  ),
                ),
                submittedPinTheme: defaultPinTheme.copyWith(
                   decoration: defaultPinTheme.decoration!.copyWith(
                    border: Border.all(color: Colors.green),
                  ),
                ),
                errorPinTheme: defaultPinTheme.copyWith(
                   decoration: defaultPinTheme.decoration!.copyWith(
                    border: Border.all(color: Colors.redAccent),
                  ),
                ),
                onCompleted: (pin) {
                   print('Confirmation Code Entered: $pin');
                   // Optionally trigger confirmation automatically
                   // _confirmSignUp();
                },
              ),
              const SizedBox(height: 40),
              _isLoading
                ? const CircularProgressIndicator()
                : ElevatedButton(
                    // Change onPressed to call _confirmSignUp
                    onPressed: _confirmSignUp,
                    style: ElevatedButton.styleFrom(
                      minimumSize: const Size(double.infinity, 50),
                      textStyle: const TextStyle(fontSize: 18)
                    ),
                    // Change button text
                    child: const Text('Confirm Account'),
                  ),
              const SizedBox(height: 15),
              // Optional Resend Code Button
               TextButton(
                 onPressed: _isLoading ? null : _resendConfirmationCode,
                 child: const Text('Resend Code'),
               ),
            ],
          ),
        ),
      ),
    );
  }
} // End of _OtpScreenState class