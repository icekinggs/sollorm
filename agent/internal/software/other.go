//go:build !windows && !linux

package software

func Collect() []Item {
	return nil
}
