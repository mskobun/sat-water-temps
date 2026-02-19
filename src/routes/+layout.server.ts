export const load = async ({ locals }: { locals: App.Locals }) => {
	const session = await locals.auth();
	return { session };
};
