<script lang="ts">
	import { signIn } from '@auth/sveltekit/client';
	import { Button } from '$lib/components/ui/button';
	import * as Card from '$lib/components/ui/card';

	function handleSignIn() {
		signIn('cognito', { callbackUrl: '/admin/jobs' });
	}
</script>

<svelte:head>
	<title>Admin Login</title>
</svelte:head>

<div class="min-h-screen bg-background flex items-center justify-center">
	<Card.Card class="w-full max-w-md mx-4">
		<Card.Header class="text-center">
			<Card.Title class="text-2xl">Admin Access</Card.Title>
			<Card.Description>Sign in to access the admin dashboard</Card.Description>
		</Card.Header>
		<Card.Content>
			<Button onclick={handleSignIn} class="w-full" size="lg">Sign in with AWS Cognito</Button>
		</Card.Content>
		<Card.Footer class="text-center text-sm text-muted-foreground">
			Protected admin area for authorized users only
		</Card.Footer>
	</Card.Card>
</div>
